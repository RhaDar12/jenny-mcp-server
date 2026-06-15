import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import nest_asyncio
nest_asyncio.apply()

from core import ensure_dirs, error_response, success_response


BRAVE_SEARCH_URL = "https://search.brave.com/search?q={query}"


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
    import os

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


def _clean_text(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def search_brave(
    query: str,
    max_results: int = 10,
    country: str = "id",
    language: str = "id-id",
    freshness: Optional[str] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Melakukan pencarian melalui halaman Brave Search menggunakan Brave Browser.
    Tidak membutuhkan Brave Search API key.
    """
    tool_name = "search_brave"

    try:
        ensure_dirs()

        query = query.strip()
        if not query:
            raise ValueError("Query pencarian tidak boleh kosong.")

        if max_results < 1 or max_results > 30:
            raise ValueError("max_results harus antara 1 sampai 30.")

        valid_freshness = {None, "pd", "pw", "pm", "py"}
        if freshness not in valid_freshness:
            raise ValueError("freshness harus: pd, pw, pm, atau py.")

        brave_path = _find_brave()
        sync_playwright = _load_playwright()

        search_url = BRAVE_SEARCH_URL.format(query=quote_plus(query))
        if freshness:
            search_url += f"&tf={freshness}"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=str(brave_path),
                headless=headless,
            )

            context = browser.new_context(
                locale=language,
                extra_http_headers={
                    "Accept-Language": language,
                },
            )

            page = context.new_page()
            response = page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            page.wait_for_timeout(1500)

            # Brave Search markup dapat berubah. Ambil kandidat link hasil utama,
            # lalu filter link internal dan duplikat.
            raw_links = page.locator("a[href]").evaluate_all(
                """elements => elements.map(a => ({
                    text: (a.innerText || a.textContent || '').trim(),
                    href: a.href,
                    aria: a.getAttribute('aria-label') || ''
                }))"""
            )

            results: List[Dict[str, Any]] = []
            seen = set()

            for item in raw_links:
                url = item.get("href") or ""
                title = _clean_text(item.get("text") or item.get("aria"))

                if not url.startswith(("http://", "https://")):
                    continue

                if "search.brave.com" in url:
                    continue

                if not title or len(title) < 3:
                    continue

                if url in seen:
                    continue

                seen.add(url)

                results.append({
                    "rank": len(results) + 1,
                    "title": title,
                    "url": url,
                    "snippet": None,
                })

                if len(results) >= max_results:
                    break

            title = page.title()
            final_url = page.url
            status_code = response.status if response else None

            browser.close()

        return success_response(
            tool=tool_name,
            message="Pencarian Brave Search berhasil",
            extra={
                "query": query,
                "engine": "Brave Search",
                "browser": "Brave",
                "brave_path": str(brave_path),
                "country": country,
                "language": language,
                "freshness": freshness,
                "requested_url": search_url,
                "final_url": final_url,
                "status_code": status_code,
                "page_title": title,
                "result_count": len(results),
                "results": results,
                "headless": headless,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)
