#!/usr/bin/env python3
"""Local-only, standard-library browser interface for Orchard Decision Audit.

No cloud, tracking, external CDNs, database writes, credentials or public bind.
Browser JSON stays within this loopback process and is not saved automatically.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parent
LIMIT = 200_000
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/sample.json": ("example_synthetic.json", "application/json; charset=utf-8")}
spec = importlib.util.spec_from_file_location("orchard_decision_engine_browser", ROOT / "decision_audit.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Don't log user-submitted numbers or confidential input.
        return

    def _valid_host(self):
        host = self.headers.get("Host", "").lower()
        port = self.server.server_address[1]
        return host in ("127.0.0.1:" + str(port), "localhost:" + str(port))

    def _headers(self, status, kind, length=0):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()

    def _send(self, status, obj):
        payload = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def do_GET(self):
        if not self._valid_host():
            self._send(403, {"error": "INVALID_HOST"})
            return
        asset = ASSETS.get(self.path)
        if asset is None:
            self._send(404, {"error": "NOT_FOUND"})
            return
        name, kind = asset
        data = (ROOT / name).read_bytes()
        self._headers(200, kind, len(data))
        self.wfile.write(data)

    def do_POST(self):
        if not self._valid_host():
            self._send(403, {"error": "INVALID_HOST"})
            return
        if self.path != "/api/analyze":
            self._send(404, {"error": "NOT_FOUND"})
            return
        origin = self.headers.get("Origin", "")
        allowed = {"http://127.0.0.1:" + str(self.server.server_address[1]),
                   "http://localhost:" + str(self.server.server_address[1])}
        if origin not in allowed:
            self._send(403, {"error": "CROSS_ORIGIN_REQUEST_BLOCKED"})
            return
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            self._send(415, {"error": "JSON_REQUIRED"})
            return
        try:
            raw_length = self.headers.get("Content-Length", "")
            if not raw_length.isdigit() or not 0 < int(raw_length) <= LIMIT:
                self._send(413, {"error": "INVALID_REQUEST_SIZE"})
                return
            raw = self.rfile.read(int(raw_length))
            data = json.loads(raw.decode("utf-8"))
            output = engine.analyze(data)
        except (ValueError, UnicodeDecodeError, OverflowError, KeyError) as exc:
            self._send(422, {"error": "INVALID_INPUT", "detail": str(exc)[:300]})
            return
        self._send(200, output)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port outside permitted range")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("ORCHARD_PRIVATE_LOCAL_URL=http://127.0.0.1:" + str(server.server_address[1]),
          flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
