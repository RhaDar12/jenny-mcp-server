from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_APPROVAL_DIR = Path(r"C:\AI-Agent\approvals")
APPROVAL_DIR = Path(
    os.environ.get(
        "JENNY_APPROVAL_DIR",
        str(DEFAULT_APPROVAL_DIR),
    )
).expanduser().resolve()

LOCK = threading.RLock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def parameters_hash(
    action: str,
    parameters: dict[str, Any],
) -> str:
    payload = {
        "action": action,
        "parameters": parameters,
    }
    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


def _ticket_path(approval_id: str) -> Path:
    clean = "".join(
        char
        for char in approval_id
        if char.isalnum() or char in {"-", "_"}
    )

    if not clean:
        raise ValueError("approval_id tidak valid.")

    return APPROVAL_DIR / f"{clean}.json"


def create_approval_request(
    *,
    action: str,
    summary: str,
    parameters: dict[str, Any],
    ttl_seconds: int = 600,
) -> dict[str, Any]:
    if ttl_seconds < 60 or ttl_seconds > 3600:
        raise ValueError(
            "ttl_seconds harus antara 60 sampai 3600."
        )

    APPROVAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    approval_id = (
        datetime.now().strftime("%Y%m%d%H%M%S")
        + "_"
        + secrets.token_hex(4)
    )
    created_at = _now()
    expires_at = created_at + timedelta(
        seconds=ttl_seconds
    )

    ticket = {
        "approval_id": approval_id,
        "status": "pending",
        "action": action,
        "summary": summary,
        "parameters_hash": parameters_hash(
            action,
            parameters,
        ),
        "parameters_preview": parameters,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "approved_at": None,
        "consumed_at": None,
        "rejected_at": None,
    }

    path = _ticket_path(approval_id)
    path.write_text(
        json.dumps(
            ticket,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "success": False,
        "tool": action,
        "message": (
            "Tindakan berisiko memerlukan persetujuan "
            "manual pengguna."
        ),
        "error": "manual_approval_required",
        "approval_id": approval_id,
        "summary": summary,
        "expires_at": expires_at.isoformat(),
        "approval_command": (
            "py C:\\AI-Agent\\mcp\\approve_mcp_action.py "
            f"approve {approval_id}"
        ),
        "inspect_command": (
            "py C:\\AI-Agent\\mcp\\approve_mcp_action.py "
            f"show {approval_id}"
        ),
    }


def load_ticket(
    approval_id: str,
) -> dict[str, Any]:
    path = _ticket_path(approval_id)

    if not path.exists():
        raise FileNotFoundError(
            f"Approval tidak ditemukan: {approval_id}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def save_ticket(
    ticket: dict[str, Any],
) -> None:
    path = _ticket_path(
        ticket["approval_id"]
    )
    path.write_text(
        json.dumps(
            ticket,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def approve_ticket(
    approval_id: str,
) -> dict[str, Any]:
    with LOCK:
        ticket = load_ticket(
            approval_id
        )

        if ticket["status"] != "pending":
            raise ValueError(
                "Approval tidak berstatus pending: "
                f"{ticket['status']}"
            )

        if _now() > datetime.fromisoformat(
            ticket["expires_at"]
        ):
            ticket["status"] = "expired"
            save_ticket(ticket)
            raise ValueError(
                "Approval sudah kedaluwarsa."
            )

        ticket["status"] = "approved"
        ticket["approved_at"] = (
            _now().isoformat()
        )
        save_ticket(ticket)
        return ticket


def reject_ticket(
    approval_id: str,
) -> dict[str, Any]:
    with LOCK:
        ticket = load_ticket(
            approval_id
        )

        if ticket["status"] not in {
            "pending",
            "approved",
        }:
            raise ValueError(
                "Approval tidak dapat ditolak dari status: "
                f"{ticket['status']}"
            )

        ticket["status"] = "rejected"
        ticket["rejected_at"] = (
            _now().isoformat()
        )
        save_ticket(ticket)
        return ticket


def consume_approval(
    *,
    approval_id: str,
    action: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    Validasi approval manual terhadap action + parameter yang persis sama.

    Ticket langsung ditandai consumed sebelum operasi dijalankan agar tidak
    dapat dipakai ulang, termasuk ketika operasi eksternal gagal.
    """
    with LOCK:
        ticket = load_ticket(
            approval_id
        )

        if ticket["status"] != "approved":
            raise PermissionError(
                "Approval belum disetujui atau sudah dipakai. "
                f"Status: {ticket['status']}"
            )

        if _now() > datetime.fromisoformat(
            ticket["expires_at"]
        ):
            ticket["status"] = "expired"
            save_ticket(ticket)
            raise PermissionError(
                "Approval sudah kedaluwarsa."
            )

        expected_hash = parameters_hash(
            action,
            parameters,
        )

        if (
            ticket["action"] != action
            or ticket["parameters_hash"]
            != expected_hash
        ):
            raise PermissionError(
                "Parameter tindakan berbeda dari approval "
                "yang disetujui."
            )

        ticket["status"] = "consumed"
        ticket["consumed_at"] = (
            _now().isoformat()
        )
        save_ticket(ticket)
        return ticket
