import ctypes
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_OUTPUT_DIR = Path(r"C:\AI-Agent\screenshots")


def _enable_dpi_awareness() -> None:
    """
    Membantu hasil screenshot sesuai ukuran layar pada Windows
    yang menggunakan display scaling.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _unique_output_path(
    output_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename:
        clean_name = Path(filename).name

        if not clean_name.lower().endswith(".png"):
            clean_name += ".png"

        candidate = output_dir / clean_name
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        candidate = output_dir / f"screenshot_{timestamp}.png"

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix

    for number in range(1, 10_000):
        alternative = candidate.with_name(
            f"{stem}_{number}{suffix}"
        )

        if not alternative.exists():
            return alternative

    raise RuntimeError(
        "Tidak dapat menentukan nama file screenshot yang unik."
    )


def _capture_with_pillow(output_path: Path) -> dict:
    from PIL import ImageGrab

    image = ImageGrab.grab(all_screens=True)
    image.save(output_path, format="PNG")

    return {
        "backend": "pillow",
        "width": image.width,
        "height": image.height,
    }


def _capture_with_mss(output_path: Path) -> dict:
    import mss
    import mss.tools

    with mss.mss() as capture:
        monitor = capture.monitors[0]
        shot = capture.grab(monitor)
        mss.tools.to_png(
            shot.rgb,
            shot.size,
            output=str(output_path),
        )

        return {
            "backend": "mss",
            "width": shot.width,
            "height": shot.height,
        }


def take_full_screenshot(
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    delay: float = 0.0,
) -> dict:
    """
    Mengambil screenshot seluruh desktop/semua monitor.

    Mencoba Pillow terlebih dahulu, kemudian MSS sebagai fallback.
    """
    try:
        _enable_dpi_awareness()

        if delay > 0:
            time.sleep(delay)

        destination = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else DEFAULT_OUTPUT_DIR.resolve()
        )

        output_path = _unique_output_path(
            destination,
            filename,
        )

        errors = []

        try:
            metadata = _capture_with_pillow(output_path)
        except Exception as exc:
            errors.append(f"Pillow: {exc}")

            try:
                metadata = _capture_with_mss(output_path)
            except Exception as mss_exc:
                errors.append(f"MSS: {mss_exc}")

                raise RuntimeError(
                    "Semua backend screenshot gagal. "
                    "Install salah satu dependency dengan: "
                    "`py -m pip install pillow mss`. "
                    f"Detail: {' | '.join(errors)}"
                ) from mss_exc

        if not output_path.exists():
            raise RuntimeError(
                "Backend selesai tetapi file screenshot tidak terbentuk."
            )

        return {
            "success": True,
            "tool": "take_full_screenshot",
            "message": "Screenshot berhasil diambil",
            "file_path": str(output_path),
            "delivered_file": {
                "status": "skipped",
                "sent_to": None,
                "sent_at": None,
                "delivery_id": None,
            },
            "error": None,
            "backend": metadata["backend"],
            "width": metadata["width"],
            "height": metadata["height"],
            "file_size_bytes": output_path.stat().st_size,
        }

    except Exception as exc:
        return {
            "success": False,
            "tool": "take_full_screenshot",
            "message": "Screenshot gagal",
            "file_path": None,
            "delivered_file": {
                "status": "failed",
                "sent_to": None,
                "sent_at": None,
                "delivery_id": None,
            },
            "error": str(exc),
        }
