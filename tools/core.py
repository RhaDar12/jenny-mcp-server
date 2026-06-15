import json
import uuid
from datetime import datetime
from pathlib import Path


BASE_DIR = Path("C:/AI-Agent")

DIRS = {
    "workspace": BASE_DIR / "workspace",
    "uploads": BASE_DIR / "uploads",
    "outputs": BASE_DIR / "outputs",
    "images": BASE_DIR / "outputs" / "images",
    "videos": BASE_DIR / "outputs" / "videos",
    "audio": BASE_DIR / "outputs" / "audio",
    "documents": BASE_DIR / "outputs" / "documents",
    "screenshots": BASE_DIR / "screenshots",
    "delivered": BASE_DIR / "delivered",
    "logs": BASE_DIR / "logs",
    "temp": BASE_DIR / "temp",
    "config": BASE_DIR / "config",
    "queues": BASE_DIR / "queues",
}


def ensure_dirs():
    """
    Membuat semua folder penting jika belum ada.
    """
    for path in DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def now_iso():
    """
    Menghasilkan waktu sekarang dalam format ISO.
    """
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix="file"):
    """
    Membuat ID unik untuk file/delivery/log.
    """
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def log_info(tool_name, message):
    """
    Menyimpan log info biasa.
    """
    ensure_dirs()
    log_path = DIRS["logs"] / "tool_info.log"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] [{tool_name}] {message}\n")


def log_error(tool_name, error):
    """
    Menyimpan log error.
    """
    ensure_dirs()
    log_path = DIRS["logs"] / "tool_error.log"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] [{tool_name}] {str(error)}\n")


def success_response(tool, message="Berhasil", file_path=None, extra=None):
    """
    Format response standar jika tool berhasil.
    """
    data = {
        "success": True,
        "tool": tool,
        "message": message,
        "file_path": str(file_path) if file_path else None,
        "delivered_file": {
            "status": "pending" if file_path else "skipped",
            "sent_to": None,
            "sent_at": None,
            "delivery_id": None
        },
        "error": None
    }

    if extra:
        data.update(extra)

    return data


def error_response(tool, error, message="Gagal menjalankan tool"):
    """
    Format response standar jika tool gagal.
    """
    log_error(tool, error)

    return {
        "success": False,
        "tool": tool,
        "message": message,
        "file_path": None,
        "delivered_file": {
            "status": "failed",
            "sent_to": None,
            "sent_at": None,
            "delivery_id": None
        },
        "error": str(error)
    }


def save_json(path, data):
    """
    Menyimpan data ke file JSON.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path, default=None):
    """
    Membaca file JSON.
    """
    path = Path(path)

    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_config():
    """
    Membaca config utama AI-Agent.
    """
    config_path = DIRS["config"] / "config.json"
    return read_json(config_path, default={})