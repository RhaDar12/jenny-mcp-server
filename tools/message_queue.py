import json
from pathlib import Path

from core import (
    DIRS,
    ensure_dirs,
    now_iso,
    make_id,
    success_response,
    error_response
)


QUEUE_FILE = DIRS["queues"] / "whatsapp_queue.jsonl"


def add_message_to_queue(
    chat_id,
    message_text=None,
    sender=None,
    message_type="text",
    file_path=None,
    raw=None
):
    """
    Menambahkan pesan WhatsApp ke queue lokal AI-Agent.
    Format disimpan sebagai JSON Lines.
    """

    tool_name = "add_message_to_queue"

    try:
        ensure_dirs()

        queue_id = make_id("queue")

        record = {
            "queue_id": queue_id,
            "chat_id": chat_id,
            "sender": sender,
            "message_type": message_type,
            "message_text": message_text,
            "file_path": file_path,
            "status": "pending",
            "created_at": now_iso(),
            "processed_at": None,
            "raw": raw
        }

        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(QUEUE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return success_response(
            tool=tool_name,
            message="Pesan berhasil ditambahkan ke queue",
            extra={
                "queue_id": queue_id,
                "queue_file": str(QUEUE_FILE),
                "record": record
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def read_queue(limit=20, status=None):
    """
    Membaca queue WhatsApp lokal.
    """

    tool_name = "read_queue"

    try:
        ensure_dirs()

        if not QUEUE_FILE.exists():
            return success_response(
                tool=tool_name,
                message="Queue masih kosong",
                extra={
                    "queue_file": str(QUEUE_FILE),
                    "items": []
                }
            )

        items = []

        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                item = json.loads(line)

                if status and item.get("status") != status:
                    continue

                items.append(item)

        items = items[-int(limit):]

        return success_response(
            tool=tool_name,
            message="Queue berhasil dibaca",
            extra={
                "queue_file": str(QUEUE_FILE),
                "count": len(items),
                "items": items
            }
        )

    except Exception as e:
        return error_response(tool_name, e)


def mark_queue_processed(queue_id):
    """
    Menandai item queue sebagai processed.
    """

    tool_name = "mark_queue_processed"

    try:
        ensure_dirs()

        if not QUEUE_FILE.exists():
            raise FileNotFoundError("Queue file belum ada")

        updated_items = []
        found = False

        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                item = json.loads(line)

                if item.get("queue_id") == queue_id:
                    item["status"] = "processed"
                    item["processed_at"] = now_iso()
                    found = True

                updated_items.append(item)

        if not found:
            raise FileNotFoundError(f"Queue ID tidak ditemukan: {queue_id}")

        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            for item in updated_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        return success_response(
            tool=tool_name,
            message="Queue berhasil ditandai processed",
            extra={
                "queue_id": queue_id
            }
        )

    except Exception as e:
        return error_response(tool_name, e)