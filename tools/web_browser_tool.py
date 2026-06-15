from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from brave_browser_tool import (
    _find_brave,
    _load_playwright,
    DEFAULT_CDP_URL,
)
from core import (
    ensure_dirs,
    error_response,
    success_response,
)


TOOL_VERSION = "1.0.0-brave-compat"
DEFAULT_OUTPUT_DIR = Path(
    r"C:\AI-Agent\outputs\web_browser"
)
VALID_WAIT_UNTIL = {
    "commit",
    "domcontentloaded",
    "load",
    "networkidle",
}


def _validate_url(
    url: str,
) -> str:
    selected = (url or "").strip()

    if not selected.startswith(
        ("http://", "https://")
    ):
        raise ValueError(
            "URL harus diawali http:// atau https://"
        )

    return selected


def _validate_wait_until(
    wait_until: str,
) -> str:
    selected = (
        wait_until
        or "domcontentloaded"
    ).strip().lower()

    if selected not in VALID_WAIT_UNTIL:
        raise ValueError(
            "wait_until harus salah satu dari: "
            "commit, domcontentloaded, load, networkidle."
        )

    return selected


def _sanitize_filename(
    value: Optional[str],
    fallback: str,
) -> str:
    cleaned = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        value or fallback,
    )
    cleaned = cleaned.strip(" ._")

    return cleaned[:120] or fallback


def _extract_page(
    page,
    *,
    max_chars: int,
    include_links: bool,
    max_links: int,
) -> Dict[str, Any]:
    body_text = (
        page.locator("body")
        .inner_text(timeout=30000)
        .strip()
    )

    original_count = len(body_text)
    truncated = (
        max_chars > 0
        and original_count > max_chars
    )
    returned_text = (
        body_text[:max_chars]
        if truncated
        else body_text
    )

    links: List[Dict[str, str]] = []

    if include_links:
        raw_links = page.locator(
            "a[href]"
        ).evaluate_all(
            """elements => elements.map(a => ({
                text: (a.innerText || a.textContent || '').trim(),
                href: a.href
            }))"""
        )

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

    return {
        "url": page.url,
        "title": page.title(),
        "text": returned_text,
        "truncated": truncated,
        "original_char_count": original_count,
        "returned_char_count": len(
            returned_text
        ),
        "links": links,
        "link_count": len(links),
    }


def _launch_browser(
    playwright,
    *,
    headless: bool,
    viewport_width: int = 1440,
    viewport_height: int = 900,
):
    brave_path = _find_brave()
    user_data = Path(r"C:\Users\r\AppData\Local\BraveSoftware\Brave-Browser\User Data")

    # Try CDP dulu — connect ke Brave yang udah running
    try:
        browser = playwright.chromium.connect_over_cdp(DEFAULT_CDP_URL)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[-1] if context.pages else context.new_page()
        return brave_path, context, page
    except Exception:
        pass  # CDP gagal, fallback ke persistent

    # Fallback: launch persistent context pake profil utama
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=str(user_data),
        executable_path=str(brave_path),
        headless=headless,
        viewport={
            "width": viewport_width,
            "height": viewport_height,
        },
        locale="id-ID",
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
    )

    page = context.pages[0] if context.pages else context.new_page()

    return brave_path, context, page


def read_web_page(
    url: str,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    max_chars: int = 50000,
    include_links: bool = True,
    max_links: int = 100,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Compatibility adapter untuk MCP `web_read`.

    Membuka Brave dalam context terisolasi, membaca teks serta link,
    lalu menutup browser.
    """
    tool_name = "read_web_page"

    try:
        ensure_dirs()

        selected_url = _validate_url(
            url,
        )
        selected_wait = _validate_wait_until(
            wait_until,
        )

        if max_chars < 0:
            raise ValueError(
                "max_chars tidak boleh negatif."
            )

        if max_links < 0 or max_links > 1000:
            raise ValueError(
                "max_links harus antara 0 sampai 1000."
            )

        sync_playwright = _load_playwright()

        with sync_playwright() as playwright:
            (
                brave_path,
                context,
                page,
            ) = _launch_browser(
                playwright,
                headless=headless,
            )

            try:
                response = page.goto(
                    selected_url,
                    wait_until=selected_wait,
                    timeout=timeout_ms,
                )

                page_data = _extract_page(
                    page,
                    max_chars=max_chars,
                    include_links=include_links,
                    max_links=max_links,
                )

                return success_response(
                    tool=tool_name,
                    message=(
                        "Halaman web berhasil dibaca "
                        "menggunakan Brave"
                    ),
                    extra={
                        **page_data,
                        "requested_url": (
                            selected_url
                        ),
                        "status_code": (
                            response.status
                            if response
                            else None
                        ),
                        "browser": "Brave",
                        "brave_path": str(
                            brave_path
                        ),
                        "headless": headless,
                        "compatibility_provider": (
                            "brave_browser_tool"
                        ),
                        "compatibility_version": (
                            TOOL_VERSION
                        ),
                    },
                )

            finally:
                context.close()

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def screenshot_web_page(
    url: str,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    full_page: bool = True,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    wait_until: str = "networkidle",
    timeout_ms: int = 45000,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Compatibility adapter untuk MCP `web_screenshot`.
    """
    tool_name = "screenshot_web_page"

    try:
        ensure_dirs()

        selected_url = _validate_url(
            url,
        )
        selected_wait = _validate_wait_until(
            wait_until,
        )

        if viewport_width < 320:
            raise ValueError(
                "viewport_width minimal 320."
            )

        if viewport_height < 240:
            raise ValueError(
                "viewport_height minimal 240."
            )

        destination = (
            Path(output_dir)
            .expanduser()
            .resolve()
            if output_dir
            else DEFAULT_OUTPUT_DIR.resolve()
        )
        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        selected_name = _sanitize_filename(
            filename,
            "web_page",
        )

        if not selected_name.lower().endswith(
            ".png"
        ):
            selected_name += ".png"

        output_path = destination / selected_name

        sync_playwright = _load_playwright()

        with sync_playwright() as playwright:
            (
                brave_path,
                context,
                page,
            ) = _launch_browser(
                playwright,
                headless=headless,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )

            try:
                response = page.goto(
                    selected_url,
                    wait_until=selected_wait,
                    timeout=timeout_ms,
                )

                page.screenshot(
                    path=str(output_path),
                    full_page=full_page,
                )

                return success_response(
                    tool=tool_name,
                    message=(
                        "Screenshot halaman web "
                        "berhasil dibuat menggunakan Brave"
                    ),
                    file_path=output_path,
                    extra={
                        "requested_url": (
                            selected_url
                        ),
                        "final_url": page.url,
                        "title": page.title(),
                        "status_code": (
                            response.status
                            if response
                            else None
                        ),
                        "screenshot_path": str(
                            output_path
                        ),
                        "full_page": full_page,
                        "viewport_width": (
                            viewport_width
                        ),
                        "viewport_height": (
                            viewport_height
                        ),
                        "browser": "Brave",
                        "brave_path": str(
                            brave_path
                        ),
                        "headless": headless,
                        "compatibility_provider": (
                            "brave_browser_tool"
                        ),
                        "compatibility_version": (
                            TOOL_VERSION
                        ),
                    },
                )

            finally:
                context.close()

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def browser_click_and_read(
    url: str,
    selector: str,
    timeout_ms: int = 30000,
    max_chars: int = 50000,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Compatibility adapter untuk MCP `web_click_read`.

    MCP server sudah mewajibkan confirm=true sebelum fungsi ini dipanggil.
    """
    tool_name = "browser_click_and_read"

    try:
        ensure_dirs()

        selected_url = _validate_url(
            url,
        )

        selected_selector = (
            selector
            or ""
        ).strip()

        if not selected_selector:
            raise ValueError(
                "selector tidak boleh kosong."
            )

        sync_playwright = _load_playwright()

        with sync_playwright() as playwright:
            (
                brave_path,
                context,
                page,
            ) = _launch_browser(
                playwright,
                headless=headless,
            )

            try:
                response = page.goto(
                    selected_url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )

                locator = page.locator(
                    selected_selector
                ).first
                locator.wait_for(
                    state="visible",
                    timeout=timeout_ms,
                )
                locator.click(
                    timeout=timeout_ms,
                )
                page.wait_for_timeout(
                    1000,
                )

                page_data = _extract_page(
                    page,
                    max_chars=max_chars,
                    include_links=True,
                    max_links=100,
                )

                return success_response(
                    tool=tool_name,
                    message=(
                        "Elemen berhasil diklik dan "
                        "halaman berhasil dibaca"
                    ),
                    extra={
                        **page_data,
                        "requested_url": (
                            selected_url
                        ),
                        "selector": (
                            selected_selector
                        ),
                        "initial_status_code": (
                            response.status
                            if response
                            else None
                        ),
                        "browser": "Brave",
                        "brave_path": str(
                            brave_path
                        ),
                        "headless": headless,
                        "compatibility_provider": (
                            "brave_browser_tool"
                        ),
                        "compatibility_version": (
                            TOOL_VERSION
                        ),
                    },
                )

            finally:
                context.close()

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )
