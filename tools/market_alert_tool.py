from core import success_response, error_response
from liquidity_sweep_strategy import analyze_liquidity_sweep
from whatsapp_text_tool import send_whatsapp_text


def build_market_alert_message(signal_output):
    """
    Membuat format pesan WhatsApp yang lebih enak dibaca.
    """

    if not signal_output:
        return "Market signal tidak menghasilkan output."

    return f"""*Jenny Market Scanner*

{signal_output}

━━━━━━━━━━━━━━
Mode: Finance API Scanner
Note: Final validation should still use broker spread, liquidity, and execution conditions."""


def send_market_signal_alert(
    symbol,
    news_status="Manual check required",
    spread_pips=None,
    target=None
):
    """
    Jalankan market scanner lalu kirim hasilnya ke WhatsApp.
    """

    tool_name = "send_market_signal_alert"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target WhatsApp chatId kosong.")

        signal_result = analyze_liquidity_sweep(
            symbol=symbol,
            news_status=news_status,
            spread_pips=spread_pips
        )

        if not signal_result.get("success"):
            return error_response(
                tool_name,
                signal_result.get("error", "Market signal gagal.")
            )

        signal_output = signal_result.get("output")

        if not signal_output:
            raise RuntimeError("Market signal berhasil tapi output kosong.")

        alert_message = build_market_alert_message(signal_output)

        send_result = send_whatsapp_text(
            target=target,
            message=alert_message
        )

        if not send_result.get("success"):
            return error_response(
                tool_name,
                send_result.get("error", "Gagal mengirim alert WhatsApp.")
            )

        return success_response(
            tool=tool_name,
            message="Market signal alert berhasil dikirim",
            extra={
                "symbol": symbol.upper().strip(),
                "news_status": news_status,
                "spread_pips": spread_pips,
                "target": target,
                "verdict": signal_result.get("verdict"),
                "signal_output": signal_output,
                "alert_message": alert_message,
                "send_result": send_result
            }
        )

    except Exception as e:
        return error_response(tool_name, e)