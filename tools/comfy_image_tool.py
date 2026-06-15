import copy
import random
import shutil
import time
import urllib.parse
from pathlib import Path

import requests

from core import (
    DIRS,
    ensure_dirs,
    make_id,
    read_json,
    success_response,
    error_response,
    load_config
)

from delivered_file import create_delivery_record


def _find_nodes_by_class(workflow, class_type):
    result = []

    for node_id, node in workflow.items():
        if node.get("class_type") == class_type:
            result.append((node_id, node))

    return result


def _set_first_node_input(workflow, class_type, input_name, value):
    nodes = _find_nodes_by_class(workflow, class_type)

    if not nodes:
        return False

    node_id, node = nodes[0]
    node.setdefault("inputs", {})
    node["inputs"][input_name] = value
    return True


def _set_prompt_texts(workflow, positive_prompt, negative_prompt):
    """
    Mengisi CLIPTextEncode.
    Biasanya ada 2 node CLIPTextEncode:
    - node pertama = positive prompt
    - node kedua = negative prompt
    """
    nodes = _find_nodes_by_class(workflow, "CLIPTextEncode")

    if len(nodes) < 1:
        raise RuntimeError("Node CLIPTextEncode tidak ditemukan di workflow.")

    nodes[0][1].setdefault("inputs", {})
    nodes[0][1]["inputs"]["text"] = positive_prompt

    if len(nodes) >= 2:
        nodes[1][1].setdefault("inputs", {})
        nodes[1][1]["inputs"]["text"] = negative_prompt


def _set_generation_params(
    workflow,
    width,
    height,
    steps,
    cfg,
    sampler_name,
    scheduler,
    seed
):
    """
    Mengatur parameter txt2img:
    - EmptyLatentImage
    - KSampler
    """

    # EmptyLatentImage
    _set_first_node_input(workflow, "EmptyLatentImage", "width", int(width))
    _set_first_node_input(workflow, "EmptyLatentImage", "height", int(height))
    _set_first_node_input(workflow, "EmptyLatentImage", "batch_size", 1)

    # KSampler
    _set_first_node_input(workflow, "KSampler", "steps", int(steps))
    _set_first_node_input(workflow, "KSampler", "cfg", float(cfg))
    _set_first_node_input(workflow, "KSampler", "sampler_name", sampler_name)
    _set_first_node_input(workflow, "KSampler", "scheduler", scheduler)
    _set_first_node_input(workflow, "KSampler", "seed", int(seed))


def _set_first_load_image(workflow, image_filename):
    """
    Mengisi node LoadImage dengan nama file gambar.
    File harus berada di folder input ComfyUI.
    """
    nodes = _find_nodes_by_class(workflow, "LoadImage")

    if not nodes:
        raise RuntimeError("Node LoadImage tidak ditemukan di workflow.")

    node_id, node = nodes[0]
    node.setdefault("inputs", {})
    node["inputs"]["image"] = image_filename
    return True


def _set_first_upscale_model(workflow, upscale_model_name):
    """
    Mengisi node UpscaleModelLoader dengan nama model upscale.
    Contoh: 4x-UltraSharp.pth
    """
    nodes = _find_nodes_by_class(workflow, "UpscaleModelLoader")

    if not nodes:
        return False

    node_id, node = nodes[0]
    node.setdefault("inputs", {})
    node["inputs"]["model_name"] = upscale_model_name
    return True


def _copy_image_to_comfy_input(image_path, comfy_input_dir, prefix="comfy_input"):
    """
    Copy gambar input ke folder input ComfyUI.
    ComfyUI LoadImage biasanya hanya membaca file dari folder input.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image input tidak ditemukan: {image_path}")

    comfy_input_dir = Path(comfy_input_dir)
    comfy_input_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{make_id(prefix)}{image_path.suffix.lower()}"
    target_path = comfy_input_dir / safe_name

    shutil.copy2(image_path, target_path)

    return target_path


def _queue_prompt(base_url, workflow, client_id):
    url = base_url.rstrip("/") + "/prompt"

    response = requests.post(
        url,
        json={
            "prompt": workflow,
            "client_id": client_id
        },
        timeout=60
    )

    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"ComfyUI /prompt error {response.status_code}: {response.text}")

    data = response.json()
    prompt_id = data.get("prompt_id")

    if not prompt_id:
        raise RuntimeError(f"ComfyUI tidak mengembalikan prompt_id: {data}")

    return prompt_id


def _wait_for_history(base_url, prompt_id, timeout=300, interval=2):
    history_url = base_url.rstrip("/") + f"/history/{prompt_id}"
    start = time.time()

    while time.time() - start < timeout:
        response = requests.get(history_url, timeout=30)

        if response.status_code == 200:
            data = response.json()

            if prompt_id in data:
                return data[prompt_id]

        time.sleep(interval)

    raise TimeoutError(f"Timeout menunggu hasil ComfyUI prompt_id: {prompt_id}")


def _get_or_download_first_output_image(base_url, history_item, output_path, comfy_output_dir=None):
    """
    Ambil image pertama dari outputs history.

    Jika file sudah ada di output_dir lokal, pakai langsung tanpa copy ulang.
    Jika tidak ada, download dari /view ke output_path.
    """
    outputs = history_item.get("outputs", {})

    for node_id, output in outputs.items():
        images = output.get("images", [])

        for image in images:
            filename = image.get("filename")
            subfolder = image.get("subfolder", "")
            image_type = image.get("type", "output")

            if not filename:
                continue

            if comfy_output_dir:
                local_file_path = Path(comfy_output_dir)

                if subfolder:
                    local_file_path = local_file_path / subfolder

                local_file_path = local_file_path / filename

                if local_file_path.exists():
                    return {
                        "file_path": str(local_file_path),
                        "filename": filename,
                        "subfolder": subfolder,
                        "type": image_type,
                        "source": "local_comfy_output",
                        "copied": False
                    }

            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type
            }

            view_url = base_url.rstrip("/") + "/view?" + urllib.parse.urlencode(params)

            response = requests.get(view_url, timeout=60)

            if response.status_code < 200 or response.status_code >= 300:
                raise RuntimeError(f"ComfyUI /view error {response.status_code}: {response.text}")

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                f.write(response.content)

            return {
                "file_path": str(output_path),
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type,
                "view_url": view_url,
                "source": "downloaded_from_comfy_view",
                "copied": True
            }

    raise RuntimeError("Tidak menemukan output image di history ComfyUI.")


def check_comfyui():
    tool_name = "check_comfyui"

    try:
        config = load_config()
        comfy_config = config.get("comfyui", {})
        base_url = comfy_config.get("base_url", "http://127.0.0.1:8188")

        url = base_url.rstrip("/") + "/object_info"
        response = requests.get(url, timeout=20)

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"ComfyUI error {response.status_code}: {response.text}")

        return success_response(
            tool=tool_name,
            message="ComfyUI API aktif",
            extra={
                "api_url": url,
                "status_code": response.status_code
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def generate_comfy_image(
    prompt,
    negative_prompt="low quality, blurry, distorted, watermark, text",
    width=None,
    height=None,
    steps=None,
    cfg=None,
    sampler_name=None,
    scheduler=None,
    seed=None,
    workflow_path=None,
    target=None,
    caption="Gambar dari ComfyUI AI-Agent"
):
    """
    Generate txt2img menggunakan workflow API ComfyUI.

    Workflow default:
    C:/AI-Agent/workflows/comfy_txt2img_api.json
    """

    tool_name = "generate_comfy_image"

    try:
        ensure_dirs()

        if not prompt or not prompt.strip():
            raise ValueError("Prompt kosong, tidak bisa generate gambar.")

        config = load_config()
        comfy_config = config.get("comfyui", {})

        base_url = comfy_config.get("base_url", "http://127.0.0.1:8188")
        workflow_path = workflow_path or comfy_config.get(
            "workflow_path",
            "C:/AI-Agent/workflows/comfy_txt2img_api.json"
        )

        width = int(width or comfy_config.get("default_width", 1024))
        height = int(height or comfy_config.get("default_height", 1024))
        steps = int(steps or comfy_config.get("default_steps", 6))
        cfg = float(cfg or comfy_config.get("default_cfg", 2))
        sampler_name = sampler_name or comfy_config.get("default_sampler", "euler")
        scheduler = scheduler or comfy_config.get("default_scheduler", "karras")

        if seed is None or str(seed) == "" or int(seed) < 0:
            seed = random.randint(1, 2**63 - 1)
        else:
            seed = int(seed)

        workflow_path = Path(workflow_path)

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow API JSON tidak ditemukan: {workflow_path}")

        workflow = read_json(workflow_path)

        if not isinstance(workflow, dict):
            raise RuntimeError("Workflow API JSON harus berupa object/dict.")

        workflow = copy.deepcopy(workflow)

        _set_prompt_texts(workflow, prompt, negative_prompt)

        _set_generation_params(
            workflow=workflow,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            sampler_name=sampler_name,
            scheduler=scheduler,
            seed=seed
        )

        client_id = make_id("comfy_client")
        prompt_id = _queue_prompt(base_url, workflow, client_id)

        history_item = _wait_for_history(
            base_url=base_url,
            prompt_id=prompt_id,
            timeout=300,
            interval=2
        )

        image_id = make_id("comfy_image")
        fallback_output_path = DIRS["images"] / f"{image_id}.png"
        comfy_output_dir = comfy_config.get("output_dir", "C:/AI-Agent/outputs/images")

        comfy_output = _get_or_download_first_output_image(
            base_url=base_url,
            history_item=history_item,
            output_path=fallback_output_path,
            comfy_output_dir=comfy_output_dir
        )

        output_path = Path(comfy_output["file_path"])

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Gambar ComfyUI berhasil dibuat",
            file_path=output_path,
            extra={
                "image_id": image_id,
                "prompt_id": prompt_id,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "seed": seed,
                "workflow_path": str(workflow_path),
                "comfy_output": comfy_output,
                "delivery_id": delivery.get("delivery_id"),
                "delivery_record": delivery.get("delivery_record"),
                "delivered_file": {
                    "status": "pending",
                    "sent_to": target,
                    "sent_at": None,
                    "delivery_id": delivery.get("delivery_id")
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def generate_comfy_img2img(
    image_path,
    prompt,
    negative_prompt="low quality, blurry, distorted, watermark, text",
    steps=None,
    cfg=None,
    sampler_name=None,
    scheduler=None,
    denoise=0.6,
    seed=None,
    workflow_path=None,
    target=None,
    caption="Gambar img2img dari ComfyUI AI-Agent"
):
    """
    Generate img2img menggunakan workflow API ComfyUI.

    Workflow default:
    C:/AI-Agent/workflows/comfy_img2img_api.json
    """

    tool_name = "generate_comfy_img2img"

    try:
        ensure_dirs()

        if not image_path or not str(image_path).strip():
            raise ValueError("Image path kosong.")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt kosong, tidak bisa generate img2img.")

        config = load_config()
        comfy_config = config.get("comfyui", {})

        base_url = comfy_config.get("base_url", "http://127.0.0.1:8188")
        workflow_path = workflow_path or comfy_config.get(
            "img2img_workflow_path",
            "C:/AI-Agent/workflows/comfy_img2img_api.json"
        )
        comfy_input_dir = comfy_config.get(
            "input_dir",
            "C:/AI-Apps/ComfyUI_windows_portable/ComfyUI/input"
        )

        steps = int(steps or comfy_config.get("default_steps", 6))
        cfg = float(cfg or comfy_config.get("default_cfg", 2))
        sampler_name = sampler_name or comfy_config.get("default_sampler", "euler")
        scheduler = scheduler or comfy_config.get("default_scheduler", "karras")
        denoise = float(denoise if denoise is not None else 0.6)

        if seed is None or str(seed) == "" or int(seed) < 0:
            seed = random.randint(1, 2**63 - 1)
        else:
            seed = int(seed)

        workflow_path = Path(workflow_path)

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow API JSON img2img tidak ditemukan: {workflow_path}")

        workflow = read_json(workflow_path)

        if not isinstance(workflow, dict):
            raise RuntimeError("Workflow API JSON harus berupa object/dict.")

        workflow = copy.deepcopy(workflow)

        comfy_input_image = _copy_image_to_comfy_input(
            image_path=image_path,
            comfy_input_dir=comfy_input_dir,
            prefix="img2img_input"
        )

        _set_first_load_image(workflow, comfy_input_image.name)
        _set_prompt_texts(workflow, prompt, negative_prompt)

        _set_first_node_input(workflow, "KSampler", "steps", int(steps))
        _set_first_node_input(workflow, "KSampler", "cfg", float(cfg))
        _set_first_node_input(workflow, "KSampler", "sampler_name", sampler_name)
        _set_first_node_input(workflow, "KSampler", "scheduler", scheduler)
        _set_first_node_input(workflow, "KSampler", "seed", int(seed))
        _set_first_node_input(workflow, "KSampler", "denoise", float(denoise))

        client_id = make_id("comfy_client")
        prompt_id = _queue_prompt(base_url, workflow, client_id)

        history_item = _wait_for_history(
            base_url=base_url,
            prompt_id=prompt_id,
            timeout=300,
            interval=2
        )

        image_id = make_id("comfy_img2img")
        fallback_output_path = DIRS["images"] / f"{image_id}.png"
        comfy_output_dir = comfy_config.get("output_dir", "C:/AI-Agent/outputs/images")

        comfy_output = _get_or_download_first_output_image(
            base_url=base_url,
            history_item=history_item,
            output_path=fallback_output_path,
            comfy_output_dir=comfy_output_dir
        )

        output_path = Path(comfy_output["file_path"])

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Gambar img2img ComfyUI berhasil dibuat",
            file_path=output_path,
            extra={
                "image_id": image_id,
                "prompt_id": prompt_id,
                "source_image_path": str(image_path),
                "comfy_input_image": str(comfy_input_image),
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler_name,
                "scheduler": scheduler,
                "denoise": denoise,
                "seed": seed,
                "workflow_path": str(workflow_path),
                "comfy_output": comfy_output,
                "delivery_id": delivery.get("delivery_id"),
                "delivery_record": delivery.get("delivery_record"),
                "delivered_file": {
                    "status": "pending",
                    "sent_to": target,
                    "sent_at": None,
                    "delivery_id": delivery.get("delivery_id")
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def generate_comfy_upscale(
    image_path,
    upscale_model=None,
    workflow_path=None,
    target=None,
    caption="Gambar upscale dari ComfyUI AI-Agent"
):
    """
    Generate upscale menggunakan workflow API ComfyUI.

    Workflow default:
    C:/AI-Agent/workflows/comfy_upscale_api.json

    Node yang diharapkan:
    - LoadImage
    - UpscaleModelLoader
    - ImageUpscaleWithModel
    - SaveImage
    """

    tool_name = "generate_comfy_upscale"

    try:
        ensure_dirs()

        if not image_path or not str(image_path).strip():
            raise ValueError("Image path kosong.")

        config = load_config()
        comfy_config = config.get("comfyui", {})

        base_url = comfy_config.get("base_url", "http://127.0.0.1:8188")
        workflow_path = workflow_path or comfy_config.get(
            "upscale_workflow_path",
            "C:/AI-Agent/workflows/comfy_upscale_api.json"
        )
        comfy_input_dir = comfy_config.get(
            "input_dir",
            "C:/AI-Apps/ComfyUI_windows_portable/ComfyUI/input"
        )
        upscale_model = upscale_model or comfy_config.get(
            "default_upscale_model",
            "4x-UltraSharp.pth"
        )

        workflow_path = Path(workflow_path)

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow API JSON upscale tidak ditemukan: {workflow_path}")

        workflow = read_json(workflow_path)

        if not isinstance(workflow, dict):
            raise RuntimeError("Workflow API JSON harus berupa object/dict.")

        workflow = copy.deepcopy(workflow)

        comfy_input_image = _copy_image_to_comfy_input(
            image_path=image_path,
            comfy_input_dir=comfy_input_dir,
            prefix="upscale_input"
        )

        _set_first_load_image(workflow, comfy_input_image.name)

        # Kalau workflow punya UpscaleModelLoader, set model-nya.
        # Kalau tidak ada, lanjut saja, karena mungkin model sudah hardcoded di workflow.
        _set_first_upscale_model(workflow, upscale_model)

        client_id = make_id("comfy_client")
        prompt_id = _queue_prompt(base_url, workflow, client_id)

        history_item = _wait_for_history(
            base_url=base_url,
            prompt_id=prompt_id,
            timeout=300,
            interval=2
        )

        image_id = make_id("comfy_upscale")
        fallback_output_path = DIRS["images"] / f"{image_id}.png"
        comfy_output_dir = comfy_config.get("output_dir", "C:/AI-Agent/outputs/images")

        comfy_output = _get_or_download_first_output_image(
            base_url=base_url,
            history_item=history_item,
            output_path=fallback_output_path,
            comfy_output_dir=comfy_output_dir
        )

        output_path = Path(comfy_output["file_path"])

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Gambar upscale ComfyUI berhasil dibuat",
            file_path=output_path,
            extra={
                "image_id": image_id,
                "prompt_id": prompt_id,
                "source_image_path": str(image_path),
                "comfy_input_image": str(comfy_input_image),
                "upscale_model": upscale_model,
                "workflow_path": str(workflow_path),
                "comfy_output": comfy_output,
                "delivery_id": delivery.get("delivery_id"),
                "delivery_record": delivery.get("delivery_record"),
                "delivered_file": {
                    "status": "pending",
                    "sent_to": target,
                    "sent_at": None,
                    "delivery_id": delivery.get("delivery_id")
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)

