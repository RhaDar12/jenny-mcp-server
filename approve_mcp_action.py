from __future__ import annotations

import argparse
import json
from pathlib import Path

from approval_store import (
    APPROVAL_DIR,
    approve_ticket,
    load_ticket,
    reject_ticket,
)


def print_json(value):
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    )


def list_tickets():
    APPROVAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    tickets = []

    for path in sorted(
        APPROVAL_DIR.glob("*.json"),
        reverse=True,
    ):
        try:
            ticket = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
            tickets.append({
                "approval_id": ticket.get(
                    "approval_id"
                ),
                "status": ticket.get(
                    "status"
                ),
                "action": ticket.get(
                    "action"
                ),
                "summary": ticket.get(
                    "summary"
                ),
                "expires_at": ticket.get(
                    "expires_at"
                ),
            })
        except Exception:
            continue

    return {
        "success": True,
        "approval_dir": str(APPROVAL_DIR),
        "tickets": tickets[:100],
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Persetujuan manual untuk tindakan "
            "berisiko Jenny MCP."
        )
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    p = sub.add_parser("show")
    p.add_argument("approval_id")

    p = sub.add_parser("approve")
    p.add_argument("approval_id")

    p = sub.add_parser("reject")
    p.add_argument("approval_id")

    sub.add_parser("list")

    args = parser.parse_args()

    try:
        if args.command == "show":
            result = load_ticket(
                args.approval_id
            )
        elif args.command == "approve":
            result = approve_ticket(
                args.approval_id
            )
        elif args.command == "reject":
            result = reject_ticket(
                args.approval_id
            )
        elif args.command == "list":
            result = list_tickets()
        else:
            raise ValueError(
                "Command tidak dikenal."
            )

        print_json({
            "success": True,
            "result": result,
        })

    except Exception as exc:
        print_json({
            "success": False,
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        })


if __name__ == "__main__":
    main()
