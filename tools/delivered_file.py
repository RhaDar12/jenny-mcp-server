from pathlib import Path
from core import (
    DIRS,
    ensure_dirs,
    now_iso,
    make_id,
    save_json,
    read_json,
    success_response,
    error_response
)


def create_delivery_record(file_path, target=None, caption=None):
    """
    Membuat catatan file yang siap dikirim.
    Status awal: pending
    """
    tool_name = "create_delivery_record"

    try:
        ensure_dirs()

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

        delivery_id = make_id("delivery")
        record_path = DIRS["delivered"] / f"{delivery_id}.json"

        record = {
            "delivery_id": delivery_id,
            "file_path": str(file_path),
            "file_name": file_path.name,
            "target": target,
            "caption": caption,
            "status": "pending",
            "created_at": now_iso(),
            "sent_at": None,
            "error": None
        }

        save_json(record_path, record)

        return success_response(
            tool=tool_name,
            message="Delivery record berhasil dibuat",
            file_path=file_path,
            extra={
                "delivery_id": delivery_id,
                "delivery_record": str(record_path),
                "delivered_file": {
                    "status": "pending",
                    "sent_to": target,
                    "sent_at": None,
                    "delivery_id": delivery_id
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def mark_delivered(delivery_id, sent_to=None):
    """
    Mengubah status file menjadi delivered.
    Dipakai setelah file benar-benar berhasil dikirim ke WhatsApp.
    """
    tool_name = "mark_delivered"

    try:
        ensure_dirs()

        record_path = DIRS["delivered"] / f"{delivery_id}.json"
        record = read_json(record_path)

        if not record:
            raise FileNotFoundError(f"Delivery record tidak ditemukan: {delivery_id}")

        if sent_to:
            record["target"] = sent_to

        record["status"] = "delivered"
        record["sent_at"] = now_iso()
        record["error"] = None

        save_json(record_path, record)

        return success_response(
            tool=tool_name,
            message="File berhasil ditandai delivered",
            file_path=record["file_path"],
            extra={
                "delivery_id": delivery_id,
                "delivery_record": str(record_path),
                "delivered_file": {
                    "status": "delivered",
                    "sent_to": record.get("target"),
                    "sent_at": record.get("sent_at"),
                    "delivery_id": delivery_id
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def mark_failed(delivery_id, error_message):
    """
    Mengubah status file menjadi failed.
    Dipakai kalau proses kirim file gagal.
    """
    tool_name = "mark_failed"

    try:
        ensure_dirs()

        record_path = DIRS["delivered"] / f"{delivery_id}.json"
        record = read_json(record_path)

        if not record:
            raise FileNotFoundError(f"Delivery record tidak ditemukan: {delivery_id}")

        record["status"] = "failed"
        record["error"] = str(error_message)

        save_json(record_path, record)

        return success_response(
            tool=tool_name,
            message="File berhasil ditandai failed",
            file_path=record["file_path"],
            extra={
                "delivery_id": delivery_id,
                "delivery_record": str(record_path),
                "delivered_file": {
                    "status": "failed",
                    "sent_to": record.get("target"),
                    "sent_at": record.get("sent_at"),
                    "delivery_id": delivery_id
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def get_delivery_record(delivery_id):
    """
    Membaca status delivery berdasarkan delivery_id.
    """
    tool_name = "get_delivery_record"

    try:
        ensure_dirs()

        record_path = DIRS["delivered"] / f"{delivery_id}.json"
        record = read_json(record_path)

        if not record:
            raise FileNotFoundError(f"Delivery record tidak ditemukan: {delivery_id}")

        return success_response(
            tool=tool_name,
            message="Delivery record ditemukan",
            file_path=record.get("file_path"),
            extra={
                "delivery_id": delivery_id,
                "delivery_record": str(record_path),
                "record": record,
                "delivered_file": {
                    "status": record.get("status"),
                    "sent_to": record.get("target"),
                    "sent_at": record.get("sent_at"),
                    "delivery_id": delivery_id
                }
            }
        )

    except Exception as e:
        return error_response(tool_name, e)