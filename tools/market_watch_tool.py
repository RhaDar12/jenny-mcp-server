import json
from datetime import datetime, timezone
from pathlib import Path

from core import success_response, error_response
from market_multi_alert_tool import parse_spread_map, build_multi_market_message
from liquidity_sweep_strategy import analyze_liquidity_sweep
from whatsapp_text_tool import send_whatsapp_text


STATE_DIR = Path("C:/AI-Agent/state")
STATE_FILE = STATE_DIR / "market_watch_state.json"

DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]


def _load_state():
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if not STATE_FILE.exists():
        return {
            "last_results": {},
            "last_alert_at": None
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "last_results": {},
            "last_alert_at": None
        }


def _save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _extract_entry_signature(result):
    """
    Signature dipakai supaya alert ENTRY yang sama tidak dikirim berulang.
    """
    symbol = result.get("symbol")
    verdict = result.get("verdict")
    output = result.get("output") or ""

    direction = None
    entry_zone = None
    stop_loss = None
    take_profit = None

    for line in output.splitlines():
        clean = line.strip()

        if clean.startswith("- Direction:"):
            direction = clean.replace("- Direction:", "").strip()

        elif clean.startswith("- Entry zone:"):
            entry_zone = clean.replace("- Entry zone:", "").strip()

        elif clean.startswith("- Stop loss:"):
            stop_loss = clean.replace("- Stop loss:", "").strip()

        elif clean.startswith("- Take profit:"):
            take_profit = clean.replace("- Take profit:", "").strip()

    return {
        "symbol": symbol,
        "verdict": verdict,
        "direction": direction,
        "entry_zone": entry_zone,
        "stop_loss": stop_loss,
        "take_profit": take_profit
    }


def _has_new_entry(results, state):
    """
    Return True jika ada ENTRY yang belum pernah dikirim.
    """
    last_results = state.get("last_results", {})

    for result in results:
        symbol = result.get("symbol")
        verdict = result.get("verdict")

        if verdict != "ENTRY":
            continue

        current_sig = _extract_entry_signature(result)
        previous_sig = last_results.get(symbol, {}).get("entry_signature")

        if current_sig != previous_sig:
            return True

    return False


def _update_state_with_results(results, state):
    now = datetime.now(timezone.utc).isoformat()

    state.setdefault("last_results", {})

    for result in results:
        symbol = result.get("symbol")
        verdict = result.get("verdict")

        state["last_results"][symbol] = {
            "verdict": verdict,
            "checked_at": now,
            "entry_signature": _extract_entry_signature(result) if verdict == "ENTRY" else None
        }

    state["last_checked_at"] = now

    return state


def run_market_watch(
    news_status="Manual check required",
    spread_text=None,
    target=None,
    symbols=None,
    send_only_on_entry=True,
    force_send=False,
    timeframe="5m"
):
    """
    Scan market M5 dan kirim WhatsApp anti-spam.

    send_only_on_entry=True:
    - kirim hanya kalau ada ENTRY baru

    force_send=True:
    - kirim ringkasan walaupun NO TRADE
    """

    tool_name = "run_market_watch"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target WhatsApp chatId kosong.")

        symbols = symbols or DEFAULT_SYMBOLS
        spread_map = parse_spread_map(spread_text)

        state = _load_state()

        results = []

        for symbol in symbols:
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
        should_send = False
        send_reason = None

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

        send_result = None

        if should_send:
            send_result = send_whatsapp_text(
                target=target,
                message=f"*Scheduled Market*\n\n{alert_message}"
            )

            if not send_result.get("success"):
                return error_response(
                    tool_name,
                    send_result.get("error", "Gagal mengirim market watch alert.")
                )

            state["last_alert_at"] = datetime.now(timezone.utc).isoformat()

        state = _update_state_with_results(results, state)
        _save_state(state)

        return success_response(
            tool=tool_name,
            message="Market watch selesai dijalankan",
            extra={
                "news_status": news_status,
                "spread_text": spread_text,
                "spread_map": spread_map,
                "target": target,
                "symbols": symbols,
                "send_only_on_entry": send_only_on_entry,
                "force_send": force_send,
                "has_new_entry": has_new_entry,
                "should_send": should_send,
                "send_reason": send_reason,
                "results": results,
                "alert_message": alert_message,
                "send_result": send_result,
                "state_file": str(STATE_FILE)
            }
        )

    except Exception as e:
        return error_response(tool_name, e)