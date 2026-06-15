from core import success_response, error_response
from mt5_liquidity_sweep_strategy import analyze_liquidity_sweep_mt5
from market_multi_alert_tool import build_multi_market_message
from whatsapp_text_tool import send_whatsapp_text
from market_watch_tool import (
    _load_state,
    _save_state,
    _has_new_entry,
    _update_state_with_results
)


DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]


def run_market_watch_mt5(
    target=None,
    symbols=None,
    send_only_on_entry=True,
    force_send=False
):
    """
    MT5 Market Watch:
    - scan XAUUSD, EURUSD, GBPUSD pakai MT5 broker data
    - pakai spread real broker
    - pakai local news filter
    - anti-spam pakai market_watch_state.json
    """

    tool_name = "run_market_watch_mt5"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target WhatsApp chatId kosong.")

        symbols = symbols or DEFAULT_SYMBOLS
        state = _load_state()
        results = []

        for symbol in symbols:
            signal = analyze_liquidity_sweep_mt5(symbol)

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

        final_message = f"""*MT5 Broker Market*

{alert_message}

Data source: MetaTrader 5 broker candles + real broker spread
Mode: MT5 Broker Scanner
"""

        send_result = None

        if should_send:
            send_result = send_whatsapp_text(
                target=target,
                message=final_message
            )

            if not send_result.get("success"):
                return error_response(
                    tool_name,
                    send_result.get("error", "Gagal mengirim MT5 market watch alert.")
                )

        state = _update_state_with_results(results, state)
        _save_state(state)

        return success_response(
            tool=tool_name,
            message="MT5 market watch selesai dijalankan",
            extra={
                "target": target,
                "symbols": symbols,
                "send_only_on_entry": send_only_on_entry,
                "force_send": force_send,
                "has_new_entry": has_new_entry,
                "should_send": should_send,
                "send_reason": send_reason,
                "results": results,
                "alert_message": final_message,
                "send_result": send_result,
                "data_source": "MT5"
            }
        )

    except Exception as e:
        return error_response(tool_name, e)