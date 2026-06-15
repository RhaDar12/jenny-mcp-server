from core import success_response, error_response
from market_multi_alert_tool import parse_spread_map, build_multi_market_message
from liquidity_sweep_strategy import analyze_liquidity_sweep
from news_filter_tool import check_high_impact_news
from whatsapp_text_tool import send_whatsapp_text
from market_watch_tool import (
    _load_state,
    _save_state,
    _has_new_entry,
    _update_state_with_results
)


DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]


def run_market_watch_auto_news(
    spread_text=None,
    target=None,
    symbols=None,
    send_only_on_entry=True,
    force_send=False,
    news_window_minutes=30
):
    """
    Market watch dengan news filter otomatis dari local economic_calendar.json.

    Flow:
    - cek news per symbol
    - pakai hasil news_status untuk analyze_liquidity_sweep
    - anti-spam pakai market_watch_state.json
    """

    tool_name = "run_market_watch_auto_news"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target WhatsApp chatId kosong.")

        symbols = symbols or DEFAULT_SYMBOLS
        spread_map = parse_spread_map(spread_text)

        state = _load_state()
        results = []
        news_results = {}

        for symbol in symbols:
            news = check_high_impact_news(
                symbol=symbol,
                window_minutes=news_window_minutes
            )

            if not news.get("success"):
                results.append({
                    "symbol": symbol,
                    "verdict": "ERROR",
                    "output": "",
                    "error": f"News filter error: {news.get('error', 'Unknown error')}"
                })
                continue

            news_status = news.get("news_status")
            news_results[symbol] = {
                "news_status": news_status,
                "matched_news": news.get("matched_news", []),
                "checked_at_utc": news.get("checked_at_utc")
            }

            spread = spread_map.get(symbol)

            signal = analyze_liquidity_sweep(
                symbol=symbol,
                news_status=news_status,
                spread_pips=spread
            )

            if not signal.get("success"):
                results.append({
                    "symbol": symbol,
                    "verdict": "ERROR",
                    "output": "",
                    "error": signal.get("error", "Unknown error")
                })
                continue

            results.append({
                "symbol": symbol,
                "verdict": signal.get("verdict"),
                "output": signal.get("output"),
                "error": None
            })

        has_new_entry = _has_new_entry(results, state)

        if force_send:
            should_send = True
            send_reason = "force_send"
        elif send_only_on_entry:
            should_send = has_new_entry
            send_reason = "new_entry" if has_new_entry else "no_new_entry"
        else:
            should_send = True
            send_reason = "send_all_scans"

        alert_message = build_multi_market_message(results)

        news_summary_lines = []
        news_summary_lines.append("*News*")

        for symbol in symbols:
            item = news_results.get(symbol)
            if not item:
                news_summary_lines.append(f"- {symbol}: Error / unavailable")
                continue

            news_summary_lines.append(f"- {symbol}: {item.get('news_status')}")

        news_summary = "\n".join(news_summary_lines)

        final_message = f"""*Scheduled Market*

{news_summary}

{alert_message}"""

        send_result = None

        if should_send:
            send_result = send_whatsapp_text(
                target=target,
                message=final_message
            )

            if not send_result.get("success"):
                return error_response(
                    tool_name,
                    send_result.get("error", "Gagal mengirim market watch auto-news alert.")
                )

        state = _update_state_with_results(results, state)
        _save_state(state)

        return success_response(
            tool=tool_name,
            message="Market watch auto-news selesai dijalankan",
            extra={
                "spread_text": spread_text,
                "spread_map": spread_map,
                "target": target,
                "symbols": symbols,
                "send_only_on_entry": send_only_on_entry,
                "force_send": force_send,
                "news_window_minutes": news_window_minutes,
                "news_results": news_results,
                "has_new_entry": has_new_entry,
                "should_send": should_send,
                "send_reason": send_reason,
                "results": results,
                "alert_message": final_message,
                "send_result": send_result
            }
        )

    except Exception as e:
        return error_response(tool_name, e)