from pathlib import Path
from typing import Optional

from core import ensure_dirs, error_response, success_response


def _load_pyperclip():
    try:
        import pyperclip
        return pyperclip
    except ImportError as exc:
        raise RuntimeError(
            "Dependency pyperclip belum terpasang. Jalankan: "
            "py -m pip install pyperclip"
        ) from exc


def read_clipboard(max_chars: int = 50000):
    tool_name = "read_clipboard"

    try:
        ensure_dirs()
        pyperclip = _load_pyperclip()
        text = pyperclip.paste()

        if text is None:
            text = ""

        original_char_count = len(text)
        truncated = max_chars > 0 and original_char_count > max_chars
        returned_text = text[:max_chars] if truncated else text

        return success_response(
            tool=tool_name,
            message="Clipboard berhasil dibaca",
            extra={
                "text": returned_text,
                "truncated": truncated,
                "original_char_count": original_char_count,
                "returned_char_count": len(returned_text),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def write_clipboard(text: str):
    tool_name = "write_clipboard"

    try:
        ensure_dirs()
        pyperclip = _load_pyperclip()
        pyperclip.copy(text)

        return success_response(
            tool=tool_name,
            message="Teks berhasil ditulis ke clipboard",
            extra={
                "char_count": len(text),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def write_file_to_clipboard(file_path: str, encoding: str = "utf-8"):
    tool_name = "write_file_to_clipboard"

    try:
        ensure_dirs()
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {path}")

        if not path.is_file():
            raise ValueError(f"Path bukan file: {path}")

        text = path.read_text(encoding=encoding)

        result = write_clipboard(text)

        if not result.get("success"):
            return result

        result["source_file"] = str(path)
        result["encoding"] = encoding
        return result

    except Exception as exc:
        return error_response(tool_name, exc)


def clear_clipboard():
    tool_name = "clear_clipboard"

    try:
        ensure_dirs()
        pyperclip = _load_pyperclip()
        pyperclip.copy("")

        return success_response(
            tool=tool_name,
            message="Clipboard berhasil dikosongkan",
            extra={
                "char_count": 0,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)
