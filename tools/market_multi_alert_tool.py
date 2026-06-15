from core import success_response, error_response
from liquidity_sweep_strategy import analyze_liquidity_sweep
from whatsapp_text_tool import send_whatsapp_text


DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]


def parse_spread_map(spread_text):
    """
    Format:
    XAUUSD=2.5,EURUSD=1.2,GBPUSD=1.5
    """
    result = {}

    if not spread_text:
        return result

    parts = str(spread_text).split(",")

    for part in parts:
        if "=" not in part:
            continue

        symbol, value = part.split("=", 1)
        symbol = symbol.strip().upper()

        try:
            result[symbol] = float(value.strip())
        except Exception:
            pass

    return result


def build_multi_market_message(results):
    lines = []
    lines.append("*Jenny Multi-Market Scanner*")
    lines.append("")
    lines.append("Strategy: Liquidity Sweep + 1:3 R:R")
    lines.append("Mode: Finance API Scanner")
    lines.append("")

    entry_found = False

    for item in results:
        symbol = item.get("symbol")
        verdict = item.get("verdict", "UNKNOWN")
        output = item.get("output", "")
        error = item.get("error")

        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"*{symbol}*")
        lines.append(f"Verdict: *{verdict}*")

        if error:
            lines.append(f"Error: {error}")
            lines.append("")
            continue

        # Ambil reason singkat dari output
        reason_line = None
        for line in output.splitlines():
            if line.startswith("REASON:"):
                reason_line = line
                break

        sweep_line = None
        for line in output.splitlines():
            if line.startswith("SWEEP CHECK:"):
                sweep_line = line
                break

        rr_line = None
        for line in output.splitlines():
            if line.startswith("R:R CALCULATION:"):
                rr_line = line
                break

        if sweep_line:
            lines.append(sweep_line)

        if rr_line:
            lines.append(rr_line)

        if reason_line:
            lines.append(reason_line)

        if verdict == "ENTRY":
            entry_found = True
            capture = False
            lines.append("")
            for line in output.splitlines():
                if line.startswith("TRADE SCENARIO:"):
                    capture = True

                if capture:
                    lines.append(line)

                if line.startswith("ALERT:"):
                    break

        lines.append("")

    lines.append("━━━━━━━━━━━━━━")

    if entry_found:
        lines.append(" Entry candidate found. Verify broker spread, liquidity, and news before entering.")
    else:
        lines.append("No valid ENTRY candidate found.")

    lines.append("")
    lines.append("I do not execute trades. User is responsible for order placement, position sizing, and brokerage conditions.")

    return "\n".join(lines)


def send_multi_market_alert(
    news_status="Manual check required",
    spread_text=None,
    target=None,
    symbols=None
):
    tool_name = "send_multi_market_alert"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target WhatsApp chatId kosong.")

        symbols = symbols or DEFAULT_SYMBOLS
        spread_map = parse_spread_map(spread_text)

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

        message = build_multi_market_message(results)

        send_result = send_whatsapp_text(
            target=target,
            message=message
        )

        if not send_result.get("success"):
            return error_response(
                tool_name,
                send_result.get("error", "Gagal mengirim multi market alert.")
            )

        return success_response(
            tool=tool_name,
            message="Multi market alert berhasil dikirim",
            extra={
                "news_status": news_status,
                "spread_text": spread_text,
                "spread_map": spread_map,
                "target": target,
                "symbols": symbols,
                "results": results,
                "alert_message": message,
                "send_result": send_result
            }
        )

    except Exception as e:
        return error_response(tool_name, e)