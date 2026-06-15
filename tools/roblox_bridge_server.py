import argparse
import json
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TOKEN_FILE = Path(r"C:\AI-Agent\config\roblox_bridge_token.txt")
MAX_BODY_BYTES = 2 * 1024 * 1024


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class State:
    def __init__(self):
        self.lock = threading.RLock()
        self.pending = deque()
        self.commands = {}
        self.plugin_last_seen = None
        self.plugin_info = {}

    def add(self, action, payload):
        command_id = uuid.uuid4().hex
        command = {
            "id": command_id,
            "action": action,
            "payload": payload or {},
            "status": "pending",
            "created_at": now_iso(),
            "dispatched_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        with self.lock:
            self.commands[command_id] = command
            self.pending.append(command_id)
        return dict(command)

    def next(self):
        with self.lock:
            self.plugin_last_seen = time.time()
            while self.pending:
                command_id = self.pending.popleft()
                command = self.commands.get(command_id)
                if not command or command["status"] != "pending":
                    continue
                command["status"] = "dispatched"
                command["dispatched_at"] = now_iso()
                return {
                    "id": command["id"],
                    "action": command["action"],
                    "payload": command["payload"],
                }
        return None

    def complete(self, command_id, success, result, error, plugin_info):
        with self.lock:
            self.plugin_last_seen = time.time()
            if isinstance(plugin_info, dict):
                self.plugin_info.update(plugin_info)
            command = self.commands.get(command_id)
            if not command:
                return None
            command["status"] = "completed" if success else "failed"
            command["completed_at"] = now_iso()
            command["result"] = result
            command["error"] = error
            return dict(command)

    def get(self, command_id):
        with self.lock:
            command = self.commands.get(command_id)
            return dict(command) if command else None

    def health(self):
        with self.lock:
            ago = None
            if self.plugin_last_seen is not None:
                ago = round(max(0.0, time.time() - self.plugin_last_seen), 3)
            return {
                "success": True,
                "service": "jenny_roblox_bridge",
                "time": now_iso(),
                "plugin_connected": ago is not None and ago <= 5,
                "plugin_last_seen_seconds_ago": ago,
                "plugin_info": dict(self.plugin_info),
                "pending_commands": sum(
                    1 for item in self.commands.values()
                    if item["status"] == "pending"
                ),
                "total_commands": len(self.commands),
            }


class Handler(BaseHTTPRequestHandler):
    server_version = "JennyRobloxBridge/1.0"

    @property
    def state(self):
        return self.server.bridge_state

    @property
    def token(self):
        return self.server.bridge_token

    def log_message(self, fmt, *args):
        print(
            f"[{self.log_date_time_string()}] "
            f"{self.client_address[0]} {fmt % args}"
        )

    def send_json(self, status, payload):
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length tidak valid.") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Body request terlalu besar.")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Body JSON harus berupa object.")
        return value

    def require_auth(self):
        if self.headers.get("X-Jenny-Token", "") == self.token:
            return True
        self.send_json(401, {"success": False, "error": "Unauthorized"})
        return False

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if path == "/health":
                self.send_json(200, self.state.health())
                return
            if not self.require_auth():
                return
            if path == "/v1/commands/next":
                self.send_json(
                    200,
                    {"success": True, "command": self.state.next()},
                )
                return
            prefix = "/v1/commands/"
            if path.startswith(prefix):
                command = self.state.get(path[len(prefix):])
                if not command:
                    self.send_json(
                        404,
                        {"success": False, "error": "Command tidak ditemukan."},
                    )
                    return
                self.send_json(200, {"success": True, "command": command})
                return
            self.send_json(
                404,
                {"success": False, "error": "Endpoint tidak ditemukan."},
            )
        except Exception as exc:
            self.send_json(500, {"success": False, "error": str(exc)})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        try:
            if not self.require_auth():
                return
            body = self.read_json()
            if path == "/v1/commands":
                action = str(body.get("action", "")).strip()
                payload = body.get("payload", {})
                if not action:
                    raise ValueError("action tidak boleh kosong.")
                if not isinstance(payload, dict):
                    raise ValueError("payload harus berupa object.")
                command = self.state.add(action, payload)
                self.send_json(201, {"success": True, "command": command})
                return
            prefix = "/v1/results/"
            if path.startswith(prefix):
                command = self.state.complete(
                    path[len(prefix):],
                    bool(body.get("success")),
                    body.get("result"),
                    str(body.get("error")) if body.get("error") else None,
                    body.get("plugin_info"),
                )
                if not command:
                    self.send_json(
                        404,
                        {"success": False, "error": "Command tidak ditemukan."},
                    )
                    return
                self.send_json(200, {"success": True, "command": command})
                return
            self.send_json(
                404,
                {"success": False, "error": "Endpoint tidak ditemukan."},
            )
        except ValueError as exc:
            self.send_json(400, {"success": False, "error": str(exc)})
        except Exception as exc:
            self.send_json(500, {"success": False, "error": str(exc)})


def load_token(token_file):
    path = Path(token_file).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Token file tidak ditemukan: {path}. Jalankan init dahulu."
        )
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Token file kosong: {path}")
    return token


def run_server(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    token_file=DEFAULT_TOKEN_FILE,
):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Bridge hanya boleh bind ke localhost.")
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.bridge_state = State()
    httpd.bridge_token = load_token(token_file)
    print(f"Jenny Roblox Bridge aktif di http://{host}:{port}")
    print("Tekan Ctrl+C untuk berhenti.")
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\nBridge dihentikan.")
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token-file", default=str(DEFAULT_TOKEN_FILE))
    args = parser.parse_args()
    run_server(args.host, args.port, Path(args.token_file))


if __name__ == "__main__":
    main()
