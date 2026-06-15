from __future__ import annotations

from typing import Any, Dict, Optional

from brave_search_tool import search_brave
from core import error_response


TOOL_VERSION = "1.0.0-brave-compat"


def _map_freshness(
    timelimit: Optional[str],
) -> Optional[str]:
    """
    Mengubah format timelimit generik menjadi format Brave Search.

    Didukung:
    d / day / pd
    w / week / pw
    m / month / pm
    y / year / py
    """
    if timelimit is None:
        return None

    value = str(timelimit).strip().lower()

    mapping = {
        "d": "pd",
        "day": "pd",
        "1d": "pd",
        "pd": "pd",
        "w": "pw",
        "week": "pw",
        "1w": "pw",
        "pw": "pw",
        "m": "pm",
        "month": "pm",
        "1m": "pm",
        "pm": "pm",
        "y": "py",
        "year": "py",
        "1y": "py",
        "py": "py",
    }

    if value not in mapping:
        raise ValueError(
            "timelimit harus salah satu dari: "
            "d, w, m, y, pd, pw, pm, atau py."
        )

    return mapping[value]


def _region_to_country_language(
    region: str,
) -> tuple[str, str]:
    """
    Mengubah region generik, misalnya id-id atau en-us,
    menjadi country dan locale untuk Brave.
    """
    clean = (region or "id-id").strip().lower()
    parts = clean.replace("_", "-").split("-")

    if len(parts) >= 2:
        language_code = parts[0]
        country_code = parts[-1]
    else:
        language_code = clean or "id"
        country_code = clean or "id"

    locale = f"{language_code}-{country_code}"

    return country_code, locale


def _add_compatibility_metadata(
    result: Dict[str, Any],
    *,
    requested_tool: str,
    region: str,
    safesearch: str,
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    result.setdefault(
        "compatibility_provider",
        "brave_search_tool.search_brave",
    )
    result.setdefault(
        "compatibility_tool",
        requested_tool,
    )
    result.setdefault(
        "compatibility_version",
        TOOL_VERSION,
    )
    result.setdefault(
        "requested_region",
        region,
    )
    result.setdefault(
        "requested_safesearch",
        safesearch,
    )
    result.setdefault(
        "safesearch_note",
        (
            "Parameter safesearch diterima untuk kompatibilitas, "
            "tetapi implementasi Brave lokal saat ini memakai "
            "pengaturan default Brave Search."
        ),
    )

    return result


def search_web(
    query: str,
    max_results: int = 10,
    region: str = "id-id",
    safesearch: str = "moderate",
    timelimit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compatibility adapter untuk MCP `web_search`.

    Backend sebenarnya adalah brave_search_tool.py yang sudah terpasang.
    """
    tool_name = "search_web"

    try:
        country, language = _region_to_country_language(
            region,
        )
        freshness = _map_freshness(
            timelimit,
        )

        result = search_brave(
            query=query,
            max_results=max_results,
            country=country,
            language=language,
            freshness=freshness,
            headless=True,
        )

        return _add_compatibility_metadata(
            result,
            requested_tool=tool_name,
            region=region,
            safesearch=safesearch,
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )


def search_news(
    query: str,
    max_results: int = 10,
    region: str = "id-id",
    safesearch: str = "moderate",
    timelimit: Optional[str] = "m",
) -> Dict[str, Any]:
    """
    Compatibility adapter untuk MCP `web_news`.

    Brave Search lokal dipakai dengan freshness filter. Query diberi
    konteks berita agar hasil lebih relevan dengan berita.
    """
    tool_name = "search_news"

    try:
        country, language = _region_to_country_language(
            region,
        )
        freshness = _map_freshness(
            timelimit,
        )

        news_query = f"{query.strip()} berita terbaru"

        result = search_brave(
            query=news_query,
            max_results=max_results,
            country=country,
            language=language,
            freshness=freshness,
            headless=True,
        )

        if isinstance(result, dict):
            result.setdefault(
                "original_query",
                query,
            )
            result.setdefault(
                "effective_query",
                news_query,
            )
            result.setdefault(
                "search_mode",
                "news_compatibility",
            )

        return _add_compatibility_metadata(
            result,
            requested_tool=tool_name,
            region=region,
            safesearch=safesearch,
        )

    except Exception as exc:
        return error_response(
            tool_name,
            exc,
        )
