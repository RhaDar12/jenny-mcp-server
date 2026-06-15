import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core import success_response, error_response


NEWS_FILE = Path("C:/AI-Agent/data/economic_calendar.json")


SYMBOL_CURRENCIES = {
    "XAUUSD": ["USD"],
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"]
}


def _load_news():
    if not NEWS_FILE.exists():
        return []

    with open(NEWS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_utc_time(value):
    value = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def check_high_impact_news(symbol, window_minutes=30):
    """
    Mengecek apakah ada high-impact news dalam window waktu tertentu.
    Default: 30 menit sebelum/sesudah waktu sekarang.
    """

    tool_name = "check_high_impact_news"

    try:
        symbol = symbol.upper().strip()

        if symbol not in SYMBOL_CURRENCIES:
            raise ValueError(f"Symbol tidak didukung: {symbol}")

        currencies = SYMBOL_CURRENCIES[symbol]
        now = datetime.now(timezone.utc)
        window = timedelta(minutes=int(window_minutes))

        news_items = _load_news()
        matched_news = []

        for item in news_items:
            impact = str(item.get("impact", "")).lower().strip()
            currency = str(item.get("currency", "")).upper().strip()

            if impact != "high":
                continue

            if currency not in currencies:
                continue

            news_time = _parse_utc_time(item.get("time_utc"))
            diff = abs(news_time - now)

            if diff <= window:
                matched_news.append({
                    "time_utc": news_time.isoformat(),
                    "currency": currency,
                    "impact": impact,
                    "event": item.get("event"),
                    "minutes_from_now": round((news_time - now).total_seconds() / 60, 2)
                })

        if matched_news:
            news_status = "Red folder within 30 mins"
        else:
            news_status = "Clear"

        return success_response(
            tool=tool_name,
            message="News filter selesai",
            extra={
                "symbol": symbol,
                "currencies_checked": currencies,
                "window_minutes": window_minutes,
                "news_status": news_status,
                "matched_news": matched_news,
                "checked_at_utc": now.isoformat()
            }
        )

    except Exception as e:
        return error_response(tool_name, e)