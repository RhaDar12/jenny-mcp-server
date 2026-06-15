from __future__ import annotations

import contextlib
import importlib
import json
import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable


SERVER_VERSION = "2.0.0-privileged-approval"
DEFAULT_TOOLS_DIR = Path(__file__).resolve().parent / "tools"
DEFAULT_LOG_DIR = Path(r"C:\AI-Agent\logs")
TOOLS_DIR = Path(
    os.environ.get("JENNY_TOOLS_DIR", str(DEFAULT_TOOLS_DIR))
).expanduser().resolve()
LOG_DIR = Path(
    os.environ.get("JENNY_MCP_LOG_DIR", str(DEFAULT_LOG_DIR))
).expanduser().resolve()

# Folder tool lama harus dapat di-import tanpa menyalin ulang semua modul.
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = logging.getLogger("jenny_mcp")
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False

if not LOGGER.handlers:
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    LOGGER.addHandler(stderr_handler)

    file_handler = RotatingFileHandler(
        LOG_DIR / "jenny_mcp.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    LOGGER.addHandler(file_handler)


# redirect_stdout bersifat global. Lock ini mencegah tool berjalan paralel
# ketika stdout sedang diarahkan ke stderr.
TOOL_CALL_LOCK = threading.RLock()


def json_safe(value: Any) -> Any:
    """Mengubah hasil tool menjadi data yang aman untuk JSON/MCP."""
    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    return str(value)


def error_result(
    tool: str,
    message: str,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "tool": tool,
        "message": message,
        "error": error or message,
        "server_version": SERVER_VERSION,
    }


def confirmation_required(
    tool: str,
    action: str,
) -> dict[str, Any]:
    return error_result(
        tool,
        (
            "Konfirmasi eksplisit pengguna diperlukan sebelum "
            f"menjalankan tindakan: {action}. "
            "Panggil ulang tool dengan confirm=true hanya setelah "
            "pengguna menyetujui tindakan tersebut."
        ),
        "confirmation_required",
    )


def require_confirmation(
    *,
    tool: str,
    action: str,
    confirm: bool,
) -> dict[str, Any] | None:
    if confirm:
        return None

    return confirmation_required(
        tool,
        action,
    )


def invoke(
    module_name: str,
    function_name: str,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Mengimpor dan menjalankan fungsi tool lama secara lazy.

    Semua output print dari modul lama dialihkan ke stderr agar tidak
    merusak protokol MCP stdio yang memakai stdout.
    """
    tool_label = f"{module_name}.{function_name}"

    with TOOL_CALL_LOCK:
        try:
            module = importlib.import_module(
                module_name
            )
            function: Callable[..., Any] = getattr(
                module,
                function_name,
            )

            LOGGER.info(
                "Calling %s",
                tool_label,
            )

            with contextlib.redirect_stdout(
                sys.stderr
            ):
                result = function(
                    *args,
                    **kwargs,
                )

            safe = json_safe(result)

            if isinstance(safe, dict):
                safe.setdefault(
                    "mcp_server_version",
                    SERVER_VERSION,
                )
                return safe

            return {
                "success": True,
                "tool": tool_label,
                "message": "Tool selesai",
                "result": safe,
                "mcp_server_version": (
                    SERVER_VERSION
                ),
            }

        except ModuleNotFoundError as exc:
            LOGGER.exception(
                "Module unavailable: %s",
                tool_label,
            )
            return error_result(
                tool_label,
                (
                    "Modul tool tidak tersedia. "
                    f"Pastikan file berada di {TOOLS_DIR}"
                ),
                str(exc),
            )

        except AttributeError as exc:
            LOGGER.exception(
                "Function unavailable: %s",
                tool_label,
            )
            return error_result(
                tool_label,
                (
                    "Fungsi belum tersedia pada versi "
                    f"tool yang terpasang: {function_name}"
                ),
                str(exc),
            )

        except Exception as exc:
            LOGGER.exception(
                "Tool failed: %s",
                tool_label,
            )
            return error_result(
                tool_label,
                "Tool gagal dijalankan",
                f"{type(exc).__name__}: {exc}",
            )


def availability_report() -> dict[str, Any]:
    """Memeriksa modul dan fungsi penting tanpa menjalankan aksinya."""
    expected = {
        "archive_tool": [
            "list_archive",
            "extract_archive",
        ],
        "document_reader_tool": [
            "read_document",
        ],
        "image_text_tool": [
            "list_ocr_languages",
            "read_image_text",
        ],
        "video_reader_tool": [
            "probe_video",
            "read_video",
        ],
        "download_tool": [
            "download_file",
        ],
        "clipboard_tool": [
            "read_clipboard",
            "write_clipboard",
            "clear_clipboard",
        ],
        "web_search_tool": [
            "search_web",
            "search_news",
        ],
        "web_browser_tool": [
            "read_web_page",
            "screenshot_web_page",
            "browser_click_and_read",
        ],
        "brave_search_tool": [
            "search_brave",
        ],
        "brave_browser_tool": [
            "open_page",
            "read_current_page",
            "fill_field",
            "click_element",
            "screenshot_current_page",
            "list_tabs",
        ],
        "github_cli_tool": [
            "check_github_tools",
            "auth_status",
            "repo_list",
            "repo_view",
            "repo_clone",
            "repo_create",
            "ssh_list_local",
            "ssh_list_remote",
            "ssh_test_github",
        ],
        "screenshot_tool": [
            "take_full_screenshot",
        ],
        "roblox_studio_tool": [
            "bridge_health",
            "send_command",
            "visual_inspect",
        ],
        "comfy_image_tool": [
            "check_comfyui",
            "generate_comfy_image",
        ],
    }

    modules: dict[str, Any] = {}

    for module_name, functions in expected.items():
        entry: dict[str, Any] = {
            "available": False,
            "functions": {},
        }

        try:
            module = importlib.import_module(
                module_name
            )
            entry["available"] = True

            for function_name in functions:
                entry["functions"][
                    function_name
                ] = hasattr(
                    module,
                    function_name,
                )

        except Exception as exc:
            entry["error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        modules[module_name] = entry

    return {
        "success": True,
        "tool": "system_status",
        "message": "Status Jenny MCP berhasil dibaca",
        "server_version": SERVER_VERSION,
        "tools_dir": str(TOOLS_DIR),
        "tools_dir_exists": TOOLS_DIR.exists(),
        "log_file": str(
            LOG_DIR / "jenny_mcp.log"
        ),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "modules": modules,
    }
