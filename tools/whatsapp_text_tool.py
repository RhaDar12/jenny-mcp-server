import requests

from core import (
    success_response,
    error_response,
    load_config
)


def send_whatsapp_text(
    target,
    message,
    gateway_url=None
):
    """
    Kirim pesan teks ke WhatsApp via Hermes WhatsApp bridge.

    Endpoint default:
    POST http://localhost:3000/send

    Payload:
    {
        "chatId": "...",
        "message": "..."
    }
    """

    tool_name = "send_whatsapp_text"

    try:
        if not target or not str(target).strip():
            raise ValueError("Target chatId kosong.")

        if not message or not str(message).strip():
            raise ValueError("Message kosong.")

        config = load_config()
        whatsapp_config = config.get("whatsapp_gateway", {})

        base_url = gateway_url or whatsapp_config.get("base_url", "http://localhost:3000")
        endpoint = whatsapp_config.get("send_text_endpoint", "/send")

        url = base_url.rstrip("/") + endpoint

        payload = {
            "chatId": target,
            "message": message
        }

        response = requests.post(
            url,
            json=payload,
            timeout=60
        )

        if response.status_code < 200 or response.status_code >= 300:
            raise RuntimeError(f"Gateway error {response.status_code}: {response.text}")

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text
            }

        return success_response(
            tool=tool_name,
            message="Pesan WhatsApp berhasil dikirim",
            extra={
                "target": target,
                "gateway_url": url,
                "gateway_response": data
            }
        )

    except Exception as e:
        return error_response(tool_name, e)