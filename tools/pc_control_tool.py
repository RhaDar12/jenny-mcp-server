import os
import time
import subprocess
from pathlib import Path

import pyautogui
import pyperclip

from core import (
    ensure_dirs,
    success_response,
    error_response
)


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


BLOCKED_COMMANDS = [
    "format",
    "del /s",
    "rmdir /s",
    "remove-item c:\\",
    "reg delete",
    "shutdown",
    "diskpart",
    "cipher",
    "takeown",
    "icacls",
]


def is_command_safe(command):
    cmd = command.lower().strip()
    return not any(blocked in cmd for blocked in BLOCKED_COMMANDS)


def get_mouse_position():
    tool_name = "get_mouse_position"

    try:
        x, y = pyautogui.position()

        return success_response(
            tool=tool_name,
            message="Posisi mouse berhasil dibaca",
            extra={
                "x": x,
                "y": y
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def click_screen(x, y, button="left", clicks=1):
    tool_name = "click_screen"

    try:
        x = int(x)
        y = int(y)
        clicks = int(clicks)

        pyautogui.click(x=x, y=y, clicks=clicks, button=button)

        return success_response(
            tool=tool_name,
            message="Klik layar berhasil",
            extra={
                "x": x,
                "y": y,
                "button": button,
                "clicks": clicks
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def move_mouse(x, y, duration=0.2):
    tool_name = "move_mouse"

    try:
        x = int(x)
        y = int(y)
        duration = float(duration)

        pyautogui.moveTo(x, y, duration=duration)

        return success_response(
            tool=tool_name,
            message="Mouse berhasil dipindahkan",
            extra={
                "x": x,
                "y": y,
                "duration": duration
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def type_text(text, interval=0.01):
    tool_name = "type_text"

    try:
        if text is None:
            raise ValueError("Text kosong")

        pyperclip.copy(str(text))
        pyautogui.hotkey("ctrl", "v")

        return success_response(
            tool=tool_name,
            message="Teks berhasil diketik",
            extra={
                "text_length": len(str(text))
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def press_key(key):
    tool_name = "press_key"

    try:
        pyautogui.press(key)

        return success_response(
            tool=tool_name,
            message="Key berhasil ditekan",
            extra={
                "key": key
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def hotkey(keys):
    tool_name = "hotkey"

    try:
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+") if k.strip()]

        if not keys:
            raise ValueError("Hotkey kosong")

        pyautogui.hotkey(*keys)

        return success_response(
            tool=tool_name,
            message="Hotkey berhasil ditekan",
            extra={
                "keys": keys
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def scroll(amount):
    tool_name = "scroll"

    try:
        amount = int(amount)
        pyautogui.scroll(amount)

        return success_response(
            tool=tool_name,
            message="Scroll berhasil",
            extra={
                "amount": amount
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def wait_seconds(seconds):
    tool_name = "wait_seconds"

    try:
        seconds = float(seconds)
        time.sleep(seconds)

        return success_response(
            tool=tool_name,
            message="Wait berhasil",
            extra={
                "seconds": seconds
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def open_path(path):
    tool_name = "open_path"

    try:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Path tidak ditemukan: {path}")

        os.startfile(str(path))

        return success_response(
            tool=tool_name,
            message="Path berhasil dibuka",
            extra={
                "path": str(path)
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def open_app(app_name):
    tool_name = "open_app"

    try:
        allowed_apps = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "explorer": "explorer.exe",
            "chrome": "chrome.exe",
            "vscode": "code",
        }

        key = app_name.lower().strip()

        if key not in allowed_apps:
            raise ValueError(
                f"App belum diizinkan: {app_name}. Allowed: {list(allowed_apps.keys())}"
            )

        subprocess.Popen(allowed_apps[key], shell=True)

        return success_response(
            tool=tool_name,
            message="Aplikasi berhasil dibuka",
            extra={
                "app_name": app_name,
                "command": allowed_apps[key]
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def run_safe_command(command, timeout=60):
    tool_name = "run_safe_command"

    try:
        if not command or not command.strip():
            raise ValueError("Command kosong")

        if not is_command_safe(command):
            raise PermissionError(f"Command diblokir demi keamanan: {command}")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=True,
            timeout=int(timeout)
        )

        return success_response(
            tool=tool_name,
            message="Command selesai dijalankan",
            extra={
                "command": command,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        )

    except Exception as e:
        return error_response(tool_name, e)