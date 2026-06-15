import ctypes
import json
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core import ensure_dirs, error_response, success_response


ROBLOX_STUDIO_TOOL_VERSION = "2.0.1-visual-screenshot-fix"

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8765"
DEFAULT_TOKEN_FILE = Path(
    r"C:\AI-Agent\config\roblox_bridge_token.txt"
)
DEFAULT_PLUGIN_TEMPLATE = Path(__file__).with_name(
    "roblox_plugin_template.lua"
)
DEFAULT_PLUGIN_OUTPUT = Path(
    r"C:\AI-Agent\roblox\JennyRobloxBridgePlugin.lua"
)
DEFAULT_SCREENSHOT_CLI = Path(__file__).with_name(
    "cli_screenshot.py"
)
DEFAULT_SCREENSHOT_OUTPUT_DIR = Path(
    r"C:\AI-Agent\screenshots"
)
DEFAULT_VISUAL_OUTPUT_DIR = Path(
    r"C:\AI-Agent\outputs\roblox_visual_inspect"
)

SUPPORTED_VIEWS = {
    "current",
    "isometric",
    "front",
    "back",
    "left",
    "right",
    "top",
}


def read_token(token_file=None):
    """
    Membaca token lokal yang dipakai oleh Python bridge dan plugin Studio.
    """
    path = (
        Path(token_file).expanduser().resolve()
        if token_file
        else DEFAULT_TOKEN_FILE.resolve()
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Token file tidak ditemukan: {path}. "
            "Jalankan init terlebih dahulu."
        )

    token = path.read_text(
        encoding="utf-8",
    ).strip()

    if not token:
        raise ValueError(
            f"Token file kosong: {path}"
        )

    return token


def request_json(
    method,
    url,
    token=None,
    payload=None,
    timeout=10,
):
    """
    Mengirim request JSON ke local Roblox bridge.
    """
    headers = {
        "Accept": "application/json",
    }
    data = None

    if token:
        headers["X-Jenny-Token"] = token

    if payload is not None:
        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers[
            "Content-Type"
        ] = "application/json; charset=utf-8"

    request = Request(
        url=url,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode(
                "utf-8",
            )

            return (
                json.loads(raw)
                if raw
                else {}
            )

    except HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"HTTP {exc.code}: "
            f"{body or exc.reason}"
        ) from exc

    except URLError as exc:
        raise ConnectionError(
            "Tidak dapat terhubung ke bridge: "
            f"{exc.reason}"
        ) from exc


def initialize_bridge(
    token_file=None,
    plugin_template=None,
    plugin_output=None,
    bridge_url=DEFAULT_BRIDGE_URL,
    rotate_token=False,
):
    """
    Membuat token lokal dan menghasilkan plugin Studio terkonfigurasi.
    """
    tool_name = "initialize_roblox_bridge"

    try:
        ensure_dirs()

        token_path = (
            Path(token_file)
            .expanduser()
            .resolve()
            if token_file
            else DEFAULT_TOKEN_FILE.resolve()
        )

        template_path = (
            Path(plugin_template)
            .expanduser()
            .resolve()
            if plugin_template
            else DEFAULT_PLUGIN_TEMPLATE.resolve()
        )

        output_path = (
            Path(plugin_output)
            .expanduser()
            .resolve()
            if plugin_output
            else DEFAULT_PLUGIN_OUTPUT.resolve()
        )

        token_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if (
            token_path.exists()
            and not rotate_token
        ):
            token = token_path.read_text(
                encoding="utf-8",
            ).strip()
        else:
            token = ""

        if not token:
            token = secrets.token_urlsafe(32)

            token_path.write_text(
                token,
                encoding="utf-8",
            )

        if not template_path.exists():
            raise FileNotFoundError(
                "Template plugin tidak ditemukan: "
                f"{template_path}"
            )

        configured_plugin = (
            template_path.read_text(
                encoding="utf-8",
            )
            .replace(
                "__BRIDGE_URL__",
                bridge_url.rstrip("/"),
            )
            .replace(
                "__BRIDGE_TOKEN__",
                token,
            )
        )

        output_path.write_text(
            configured_plugin,
            encoding="utf-8",
        )

        return success_response(
            tool=tool_name,
            message=(
                "Bridge Roblox berhasil "
                "diinisialisasi"
            ),
            file_path=output_path,
            extra={
                "version": (
                    ROBLOX_STUDIO_TOOL_VERSION
                ),
                "bridge_url": (
                    bridge_url.rstrip("/")
                ),
                "token_file": str(token_path),
                "token_exposed": False,
                "plugin_output": str(
                    output_path
                ),
                "rotate_token": bool(
                    rotate_token
                ),
            },
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def bridge_health(
    bridge_url=DEFAULT_BRIDGE_URL,
):
    """
    Membaca status local bridge dan koneksi plugin.
    """
    tool_name = "roblox_bridge_health"

    try:
        result = request_json(
            "GET",
            bridge_url.rstrip("/")
            + "/health",
        )

        return success_response(
            tool=tool_name,
            message=(
                "Status bridge berhasil dibaca"
            ),
            extra={
                "version": (
                    ROBLOX_STUDIO_TOOL_VERSION
                ),
                "health": result,
            },
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def command_status(
    command_id,
    bridge_url=DEFAULT_BRIDGE_URL,
    token_file=None,
):
    """
    Membaca status satu command Studio.
    """
    tool_name = "roblox_command_status"

    try:
        result = request_json(
            "GET",
            (
                f"{bridge_url.rstrip('/')}"
                f"/v1/commands/{command_id}"
            ),
            token=read_token(
                token_file,
            ),
        )

        return success_response(
            tool=tool_name,
            message=(
                "Status command berhasil dibaca"
            ),
            extra=result,
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def send_command(
    action,
    payload=None,
    bridge_url=DEFAULT_BRIDGE_URL,
    token_file=None,
    wait=True,
    wait_timeout=30,
    poll_interval=0.25,
):
    """
    Mengirim command ke plugin Roblox Studio.
    """
    tool_name = (
        "send_roblox_studio_command"
    )

    try:
        token = read_token(
            token_file,
        )

        response = request_json(
            "POST",
            (
                bridge_url.rstrip("/")
                + "/v1/commands"
            ),
            token=token,
            payload={
                "action": action,
                "payload": payload or {},
            },
        )

        command = response.get(
            "command",
        )

        if not isinstance(
            command,
            dict,
        ):
            raise RuntimeError(
                "Bridge tidak mengembalikan "
                "command yang valid."
            )

        command_id = command["id"]

        if not wait:
            return success_response(
                tool=tool_name,
                message=(
                    "Command berhasil masuk antrean"
                ),
                extra={
                    "command_id": command_id,
                    "command": command,
                    "waited": False,
                },
            )

        deadline = (
            time.monotonic()
            + wait_timeout
        )
        latest = command

        while (
            time.monotonic()
            < deadline
        ):
            status_result = request_json(
                "GET",
                (
                    f"{bridge_url.rstrip('/')}"
                    f"/v1/commands/"
                    f"{command_id}"
                ),
                token=token,
            )

            latest = status_result.get(
                "command",
                latest,
            )

            status = latest.get(
                "status",
            )

            if status in {
                "completed",
                "failed",
            }:
                return success_response(
                    tool=tool_name,
                    message=(
                        "Command Studio selesai"
                        if status == "completed"
                        else "Command Studio gagal"
                    ),
                    extra={
                        "command_id": (
                            command_id
                        ),
                        "command": latest,
                        "waited": True,
                    },
                )

            time.sleep(
                poll_interval,
            )

        return success_response(
            tool=tool_name,
            message=(
                "Command masih menunggu "
                "Roblox Studio"
            ),
            extra={
                "command_id": command_id,
                "command": latest,
                "waited": True,
                "timed_out": True,
            },
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def _require_completed_command(
    result,
):
    """
    Memastikan respons dari send_command benar-benar completed.
    """
    if not result.get(
        "success",
    ):
        raise RuntimeError(
            result.get(
                "error",
                "Command bridge gagal.",
            )
        )

    command = result.get(
        "command",
    )

    if not isinstance(
        command,
        dict,
    ):
        raise RuntimeError(
            "Respons command tidak valid."
        )

    status = command.get(
        "status",
    )

    if status != "completed":
        raise RuntimeError(
            command.get("error")
            or (
                "Command tidak selesai. "
                f"Status: {status}"
            )
        )

    return command


def _parse_cli_json_output(
    output_text,
):
    """
    Membaca JSON dari stdout CLI.

    Perbaikan utama:
    versi lama memilih object JSON TERAKHIR. Karena output screenshot
    memiliki nested object `delivered_file`, yang terpilih justru object
    tersebut dan bukan object utama. Akibatnya key `success` tidak ada
    dan Visual Inspect selalu menganggap screenshot gagal.

    Versi ini:
    1. Mencoba json.loads terhadap seluruh stdout.
    2. Jika stdout mengandung log tambahan, mencari seluruh object JSON.
    3. Memilih object terluar/terpanjang yang memiliki key `success`.
    """
    text = (
        output_text
        or ""
    ).strip()

    if not text:
        raise ValueError(
            "Screenshot CLI tidak "
            "menghasilkan stdout."
        )

    try:
        value = json.loads(
            text,
        )

        if isinstance(
            value,
            dict,
        ):
            return value

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    candidates = []

    for index, char in enumerate(
        text,
    ):
        if char != "{":
            continue

        try:
            value, end_offset = (
                decoder.raw_decode(
                    text[index:],
                )
            )
        except json.JSONDecodeError:
            continue

        if not isinstance(
            value,
            dict,
        ):
            continue

        candidates.append({
            "value": value,
            "start": index,
            "length": end_offset,
            "has_success": (
                "success" in value
            ),
            "has_tool": (
                "tool" in value
            ),
            "has_file_path": (
                "file_path" in value
            ),
        })

    if not candidates:
        raise ValueError(
            "Output screenshot CLI tidak "
            "mengandung JSON object valid."
        )

    preferred = [
        item
        for item in candidates
        if item["has_success"]
        and (
            item["has_tool"]
            or item["has_file_path"]
        )
    ]

    pool = (
        preferred
        if preferred
        else candidates
    )

    selected = max(
        pool,
        key=lambda item: (
            item["length"],
            -item["start"],
        ),
    )

    return selected["value"]


def _safe_filename_fragment(
    value,
):
    """
    Mengubah teks menjadi bagian nama file yang aman.
    """
    cleaned = "".join(
        char
        if (
            char.isalnum()
            or char in {"-", "_"}
        )
        else "_"
        for char in str(value)
    )

    cleaned = cleaned.strip("_")

    return (
        cleaned[:80]
        or "capture"
    )


def _take_full_screenshot(
    screenshot_cli=None,
    output_dir=None,
    filename=None,
    delay=0.2,
):
    """
    Menjalankan cli_screenshot.py sebagai subprocess dan membaca
    object JSON utama secara benar.
    """
    cli_path = (
        Path(screenshot_cli)
        .expanduser()
        .resolve()
        if screenshot_cli
        else DEFAULT_SCREENSHOT_CLI.resolve()
    )

    if not cli_path.exists():
        raise FileNotFoundError(
            "Screenshot CLI tidak ditemukan: "
            f"{cli_path}"
        )

    command = [
        sys.executable,
        str(cli_path),
        "full",
    ]

    if output_dir:
        destination = (
            Path(output_dir)
            .expanduser()
            .resolve()
        )

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        command.extend([
            "--output-dir",
            str(destination),
        ])

    if filename:
        command.extend([
            "--filename",
            str(filename),
        ])

    if delay and delay > 0:
        command.extend([
            "--delay",
            str(float(delay)),
        ])

    creation_flags = 0

    if (
        sys.platform == "win32"
        and hasattr(
            subprocess,
            "CREATE_NO_WINDOW",
        )
    ):
        creation_flags = (
            subprocess.CREATE_NO_WINDOW
        )

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        cwd=str(
            cli_path.parent,
        ),
        creationflags=creation_flags,
    )

    stdout = (
        process.stdout
        or ""
    ).strip()
    stderr = (
        process.stderr
        or ""
    ).strip()

    if process.returncode != 0:
        raise RuntimeError(
            "Screenshot CLI gagal. "
            f"Exit code: {process.returncode}. "
            f"stdout: {stdout or '-'} | "
            f"stderr: {stderr or '-'}"
        )

    result = _parse_cli_json_output(
        stdout,
    )

    if not result.get(
        "success",
    ):
        raise RuntimeError(
            "Screenshot gagal: "
            + str(
                result.get("error")
                or result.get("message")
                or stdout
            )
        )

    file_path = result.get(
        "file_path",
    )

    if not file_path:
        raise RuntimeError(
            "Screenshot berhasil tetapi "
            "file_path tidak ditemukan. "
            f"Output: {stdout}"
        )

    screenshot_path = (
        Path(file_path)
        .expanduser()
    )

    if not screenshot_path.exists():
        raise RuntimeError(
            "Screenshot CLI melaporkan berhasil, "
            "tetapi file tidak ditemukan: "
            f"{screenshot_path}"
        )

    result[
        "file_path"
    ] = str(
        screenshot_path.resolve()
    )

    return result


def _focus_roblox_studio_window():
    """
    Membawa jendela Roblox Studio ke depan memakai Win32 API.

    Fungsi ini tidak melakukan klik, mengetik, atau interaksi lain.
    """
    if sys.platform != "win32":
        return {
            "attempted": False,
            "focused": False,
            "reason": "Bukan Windows.",
        }

    user32 = ctypes.windll.user32

    target = {
        "hwnd": None,
        "title": None,
    }

    enum_windows_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )

    def callback(
        hwnd,
        _,
    ):
        if not user32.IsWindowVisible(
            hwnd,
        ):
            return True

        length = (
            user32.GetWindowTextLengthW(
                hwnd,
            )
        )

        if length <= 0:
            return True

        buffer = (
            ctypes.create_unicode_buffer(
                length + 1,
            )
        )

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1,
        )

        title = buffer.value

        if (
            "Roblox Studio"
            in title
        ):
            target["hwnd"] = hwnd
            target["title"] = title
            return False

        return True

    user32.EnumWindows(
        enum_windows_proc(
            callback,
        ),
        0,
    )

    hwnd = target["hwnd"]

    if not hwnd:
        return {
            "attempted": True,
            "focused": False,
            "reason": (
                "Jendela Roblox Studio "
                "tidak ditemukan."
            ),
        }

    sw_restore = 9

    user32.ShowWindow(
        hwnd,
        sw_restore,
    )

    focused = bool(
        user32.SetForegroundWindow(
            hwnd,
        )
    )

    return {
        "attempted": True,
        "focused": focused,
        "window_title": (
            target["title"]
        ),
    }


def visual_inspect(
    path=None,
    *,
    use_selection=False,
    views=None,
    padding=1.25,
    screenshot=True,
    screenshot_cli=None,
    settle_seconds=1.25,
    bridge_url=DEFAULT_BRIDGE_URL,
    token_file=None,
    wait_timeout=30,
    output_dir=None,
):
    """
    Workflow Visual Inspect:

    1. Memilih target Instance.
    2. Mengatur camera Studio.
    3. Membawa Studio ke foreground.
    4. Mengambil screenshot per view.
    5. Menyimpan manifest JSON.
    """
    tool_name = (
        "roblox_visual_inspect"
    )

    try:
        ensure_dirs()

        if (
            use_selection
            and path
        ):
            raise ValueError(
                "Gunakan path atau "
                "use_selection, jangan keduanya."
            )

        if (
            not use_selection
            and not path
        ):
            raise ValueError(
                "path wajib diisi jika "
                "tidak memakai selection."
            )

        selected_views = (
            views
            or ["isometric"]
        )

        if isinstance(
            selected_views,
            str,
        ):
            selected_views = [
                item.strip().lower()
                for item in (
                    selected_views.split(",")
                )
                if item.strip()
            ]

        if not selected_views:
            raise ValueError(
                "Minimal satu view diperlukan."
            )

        invalid_views = [
            view
            for view in selected_views
            if view not in SUPPORTED_VIEWS
        ]

        if invalid_views:
            raise ValueError(
                "View tidak didukung: "
                f"{invalid_views}. "
                "Gunakan: "
                f"{sorted(SUPPORTED_VIEWS)}"
            )

        if (
            padding < 1.0
            or padding > 5.0
        ):
            raise ValueError(
                "padding harus antara "
                "1.0 sampai 5.0."
            )

        manifest_dir = (
            Path(output_dir)
            .expanduser()
            .resolve()
            if output_dir
            else DEFAULT_VISUAL_OUTPUT_DIR.resolve()
        )

        manifest_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        screenshot_dir = (
            DEFAULT_SCREENSHOT_OUTPUT_DIR
            .resolve()
        )

        screenshot_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        session_id = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )

        captures = []

        for index, view in enumerate(
            selected_views,
            start=1,
        ):
            action = (
                "visual_inspect_selection"
                if use_selection
                else "visual_inspect_prepare"
            )

            payload = {
                "view": view,
                "padding": padding,
            }

            if not use_selection:
                payload["path"] = path

            command_result = send_command(
                action=action,
                payload=payload,
                bridge_url=bridge_url,
                token_file=token_file,
                wait=True,
                wait_timeout=wait_timeout,
            )

            completed_command = (
                _require_completed_command(
                    command_result,
                )
            )

            focus_result = (
                _focus_roblox_studio_window()
            )

            time.sleep(
                max(
                    0.0,
                    float(settle_seconds),
                )
            )

            screenshot_result = None

            if screenshot:
                target_fragment = (
                    "selection"
                    if use_selection
                    else _safe_filename_fragment(
                        path,
                    )
                )

                screenshot_filename = (
                    "roblox_visual_"
                    f"{session_id}_"
                    f"{index:02d}_"
                    f"{target_fragment}_"
                    f"{_safe_filename_fragment(view)}"
                    ".png"
                )

                screenshot_result = (
                    _take_full_screenshot(
                        screenshot_cli=(
                            screenshot_cli
                        ),
                        output_dir=(
                            screenshot_dir
                        ),
                        filename=(
                            screenshot_filename
                        ),
                        delay=0.2,
                    )
                )

            captures.append({
                "view": view,
                "studio_command": (
                    completed_command
                ),
                "window_focus": (
                    focus_result
                ),
                "screenshot": (
                    screenshot_result
                ),
                "screenshot_path": (
                    screenshot_result.get(
                        "file_path"
                    )
                    if screenshot_result
                    else None
                ),
            })

        screenshot_paths = [
            capture[
                "screenshot_path"
            ]
            for capture in captures
            if capture.get(
                "screenshot_path"
            )
        ]

        manifest = {
            "version": (
                ROBLOX_STUDIO_TOOL_VERSION
            ),
            "session_id": session_id,
            "target_path": path,
            "used_selection": bool(
                use_selection
            ),
            "views": selected_views,
            "padding": padding,
            "captures": captures,
            "screenshot_paths": (
                screenshot_paths
            ),
            "screenshot_count": len(
                screenshot_paths
            ),
            "vision_next_step": (
                "Analyze every screenshot_path "
                "using the available Vision or "
                "Image Analysis tool."
            ),
        }

        manifest_path = (
            manifest_dir
            / (
                "visual_inspect_"
                f"{session_id}.json"
            )
        )

        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return success_response(
            tool=tool_name,
            message=(
                "Visual inspect Roblox Studio "
                "berhasil"
            ),
            file_path=manifest_path,
            extra={
                **manifest,
                "manifest_path": str(
                    manifest_path
                ),
            },
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )
