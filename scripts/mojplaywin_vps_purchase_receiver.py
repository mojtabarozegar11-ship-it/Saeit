"""Loopback-only HMAC purchase event receiver for staged MojPlayWin checkout.

This receiver MUST remain bound to 127.0.0.1. Remote Django traffic may reach
it only after a separately reviewed, TLS-authenticated HTTPS reverse proxy
is installed. No public HTTP, no database writes and no payment approvals.

Environment MPW_NATIVE_EVENT_SECRET must be provisioned securely on the VPS.
NEVER commit or print that value. No AI/OpenAI API calls are made.
"""
import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.mojplaywin_purchase_events import (
    EventRejected, MAX_EVENT_BYTES, handle_verified_event,
)

ALLOWED_PATH = "/api/mpw/native-watch-event"


class LocalOnlyHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, handler_type, *, home, signing_key):
        if address[0] != "127.0.0.1":
            raise ValueError("Receiver must be bound to IPv4 loopback only")
        if not isinstance(signing_key, bytes) or len(signing_key) < 32:
            raise ValueError("Event signing key not provisioned")
        self.home = Path(home)
        self.signing_key = signing_key
        super().__init__(address, handler_type)


class EventHTTPHandler(BaseHTTPRequestHandler):
    server_version = "MPWEvent/1"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        # No headers, signatures, address details or payload in logs.
        return

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply(404, b'{"status":"not_found"}')

    def do_POST(self):
        if self.path != ALLOWED_PATH:
            self._reply(404, b'{"status":"not_found"}')
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._reply(415, b'{"status":"unsupported_media_type"}')
            return
        content_length = self.headers.get("Content-Length")
        if not isinstance(content_length, str) or not re.fullmatch(r"[0-9]{1,4}", content_length):
            self._reply(411, b'{"status":"length_required"}')
            return
        size = int(content_length)
        if size <= 0 or size > MAX_EVENT_BYTES:
            self._reply(413, b'{"status":"payload_rejected"}')
            return
        signature = self.headers.get("X-MPW-Signature", "")
        body = self.rfile.read(size)
        try:
            result = handle_verified_event(
                body, signature, self.server.signing_key, self.server.home,
            )
        except (EventRejected, OSError, ValueError):
            self._reply(403, b'{"status":"rejected"}')
            return
        answer = json.dumps({
            "status": "accepted",
            "state": result["state"],
        }, separators=(",", ":")).encode("ascii")
        self._reply(200, answer)


def main():
    parser = argparse.ArgumentParser(
        description="Local-only MojPlayWin authenticated purchase events",
    )
    parser.add_argument("--home", required=True)
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        parser.error("Invalid listener port")
    secret = os.environ.get("MPW_NATIVE_EVENT_SECRET")
    if not secret or len(secret.encode("utf-8")) < 32:
        parser.error("HMAC event key missing; receiver remains disabled")
    os.umask(0o077)
    server = LocalOnlyHTTPServer(
        ("127.0.0.1", args.port), EventHTTPHandler,
        home=args.home, signing_key=secret.encode("utf-8"),
    )
    try:
        print("MPW_LOCAL_EVENT_RECEIVER_ACTIVE_LOOPBACK_ONLY", flush=True)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
