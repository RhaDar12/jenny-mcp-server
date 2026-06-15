import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import nest_asyncio

nest_asyncio.apply()

from core import ensure_dirs, error_response, success_response


DEFAULT_PROFILE_DIR = Path(r"C:\Users\r\AppData\Local\BraveSoftware\Brave-Browser\User Data")
DEFAULT_OUTPUT_DIR = Path(r"C:\AI-Agent\outputs\brave_browser")
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
BRAVE_BROWSER_TOOL_VERSION = "2026.06.13-playwright-stop-fix"


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright belum terpasang. Jalankan:\n"
            "py -m pip install playwright\n"
            "py -m playwright install chromium"
        ) from exc


def _find_brave() -> Path:
    candidates = []

    custom = os.environ.get("BRAVE_CMD")
    if custom:
        candidates.append(Path(custom).expanduser())

    candidates.extend([
        Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"),
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
            )
        ),
    ])

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Brave Browser tidak ditemukan. Set BRAVE_CMD atau install Brave."
    )


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name or "")
    cleaned = cleaned.strip(" ._")
    return cleaned[:120] or "brave_page"


def _get_active_page(context):
    pages = context.pages

    if pages:
        return pages[-1]

    return context.new_page()


class BraveSession:
    """
    Session controller.

    Mode persistent:
      Membuka Brave baru memakai profil khusus Jenny.

    Mode CDP:
      Menempel ke Brave yang sebelumnya dijalankan dengan
      --remote-debugging-port=9222.
    """

    def __init__(
        self,
        mode: str = "cdp",
        profile_dir: Optional[str] = None,
        cdp_url: str = DEFAULT_CDP_URL,
        headless: bool = False,
    ):
        self.mode = mode
        self.profile_dir = (
            Path(profile_dir).expanduser().resolve()
            if profile_dir
            else DEFAULT_PROFILE_DIR.resolve()
        )
        self.cdp_url = cdp_url
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        sync_playwright = _load_playwright()
        self.playwright = sync_playwright().start()

        if self.mode == "persistent":
            brave_path = _find_brave()
            self.profile_dir.mkdir(parents=True, exist_ok=True)

            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                executable_path=str(brave_path),
                headless=self.headless,
                viewport={"width": 1440, "height": 900},
                locale="id-ID",
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self.page = _get_active_page(self.context)

        elif self.mode == "cdp":
            self.browser = self.playwright.chromium.connect_over_cdp(
                self.cdp_url
            )

            contexts = self.browser.contexts
            if not contexts:
                raise RuntimeError(
                    "Brave terhubung tetapi tidak memiliki browser context."
                )

            self.context = contexts[0]
            self.page = _get_active_page(self.context)

        else:
            raise ValueError("mode harus persistent atau cdp.")

        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.mode == "persistent" and self.context:
                # Persistent context milik proses ini, jadi boleh ditutup.
                self.context.close()

            # Pada mode CDP jangan panggil browser.close(), karena itu dapat
            # menutup Brave milik pengguna. Menghentikan Playwright cukup
            # untuk memutus koneksi automation.
        finally:
            if self.playwright:
                self.playwright.stop()


def open_page(
    url: str,
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 45000,
) -> Dict[str, Any]:
    tool_name = "brave_open_page"

    try:
        ensure_dirs()

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            response = session.page.goto(
                url,
                wait_until=wait_until,
                timeout=timeout_ms,
            )

            return success_response(
                tool=tool_name,
                message="Halaman berhasil dibuka di Brave",
                extra={
                    "mode": mode,
                    "requested_url": url,
                    "final_url": session.page.url,
                    "title": session.page.title(),
                    "status_code": response.status if response else None,
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)


def read_current_page(
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    max_chars: int = 50000,
    max_links: int = 100,
) -> Dict[str, Any]:
    tool_name = "brave_read_current_page"

    try:
        ensure_dirs()

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            page = session.page
            body_text = page.locator("body").inner_text(timeout=30000).strip()

            original_count = len(body_text)
            truncated = max_chars > 0 and original_count > max_chars
            text = body_text[:max_chars] if truncated else body_text

            raw_links = page.locator("a[href]").evaluate_all(
                """elements => elements.map(a => ({
                    text: (a.innerText || a.textContent || '').trim(),
                    href: a.href
                }))"""
            )

            links: List[Dict[str, str]] = []
            seen = set()

            for item in raw_links:
                href = item.get("href")
                if not href or href in seen:
                    continue

                seen.add(href)
                links.append({
                    "text": item.get("text", ""),
                    "url": href,
                })

                if len(links) >= max_links:
                    break

            return success_response(
                tool=tool_name,
                message="Halaman Brave berhasil dibaca secara real time",
                extra={
                    "mode": mode,
                    "url": page.url,
                    "title": page.title(),
                    "text": text,
                    "truncated": truncated,
                    "original_char_count": original_count,
                    "returned_char_count": len(text),
                    "links": links,
                    "link_count": len(links),
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)


def fill_field(
    selector: str,
    value: str,
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    clear_first: bool = True,
) -> Dict[str, Any]:
    tool_name = "brave_fill_field"

    try:
        ensure_dirs()

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            locator = session.page.locator(selector).first
            locator.wait_for(state="visible", timeout=30000)

            if clear_first:
                locator.fill("")
                locator.fill(value)
            else:
                locator.press_sequentially(value)

            return success_response(
                tool=tool_name,
                message="Form field berhasil diisi",
                extra={
                    "mode": mode,
                    "url": session.page.url,
                    "title": session.page.title(),
                    "selector": selector,
                    "char_count": len(value),
                    "clear_first": clear_first,
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)


def click_element(
    selector: str,
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    wait_after_ms: int = 1000,
) -> Dict[str, Any]:
    tool_name = "brave_click_element"

    try:
        ensure_dirs()

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            locator = session.page.locator(selector).first
            locator.wait_for(state="visible", timeout=30000)
            locator.click(timeout=30000)
            session.page.wait_for_timeout(wait_after_ms)

            return success_response(
                tool=tool_name,
                message="Elemen berhasil diklik",
                extra={
                    "mode": mode,
                    "selector": selector,
                    "url": session.page.url,
                    "title": session.page.title(),
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)


def screenshot_current_page(
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
    full_page: bool = True,
) -> Dict[str, Any]:
    tool_name = "brave_screenshot_current_page"

    try:
        ensure_dirs()

        destination = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else DEFAULT_OUTPUT_DIR.resolve()
        )
        destination.mkdir(parents=True, exist_ok=True)

        selected_name = _sanitize_filename(filename or "brave_current_page")
        if not selected_name.lower().endswith(".png"):
            selected_name += ".png"

        output_path = destination / selected_name

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            session.page.screenshot(
                path=str(output_path),
                full_page=full_page,
            )

            return success_response(
                tool=tool_name,
                message="Screenshot Brave berhasil dibuat",
                file_path=output_path,
                extra={
                    "mode": mode,
                    "url": session.page.url,
                    "title": session.page.title(),
                    "screenshot_path": str(output_path),
                    "full_page": full_page,
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)


def list_tabs(
    mode: str = "cdp",
    profile_dir: Optional[str] = None,
    cdp_url: str = DEFAULT_CDP_URL,
) -> Dict[str, Any]:
    tool_name = "brave_list_tabs"

    try:
        ensure_dirs()

        with BraveSession(
            mode=mode,
            profile_dir=profile_dir,
            cdp_url=cdp_url,
            headless=False,
        ) as session:
            tabs = []

            for index, page in enumerate(session.context.pages):
                tabs.append({
                    "index": index,
                    "url": page.url,
                    "title": page.title(),
                })

            return success_response(
                tool=tool_name,
                message="Daftar tab Brave berhasil dibaca",
                extra={
                    "mode": mode,
                    "tab_count": len(tabs),
                    "tabs": tabs,
                },
            )

    except Exception as exc:
        return error_response(tool_name, exc)
