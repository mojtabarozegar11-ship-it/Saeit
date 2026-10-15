#!/usr/bin/env python3
"""127.0.0.1-only interactive water-land research tool; no remote services.

Neither this local HTTP listener nor its browser UI can verify farmer inputs,
customer demand, water rights or sale/publishing eligibility.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re

from water_margin_audit import audit, ModelInputError

HERE = Path(__file__).resolve().parent
MAX_REQUEST = 150_000
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/sample.json": ("example_synthetic.json", "application/json; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # User inputs and paths must not leak into access logs.
        pass

    def _allowed_host(self):
        port = self.server.server_address[1]
        return self.headers.get_all("Host", []) in (
            [f"127.0.0.1:{port}"], [f"localhost:{port}"])

    def _valid_origin(self):
        port = self.server.server_address[1]
        return self.headers.get_all("Origin", []) in (
            [f"http://127.0.0.1:{port}"], [f"http://localhost:{port}"])

    def _respond(self, status, payload, media_type):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status, result):
        data = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self._respond(status, data, "application/json; charset=utf-8")

    def do_GET(self):
        if not self._allowed_host():
            self._json(403, {"error": "INVALID_HOST"})
            return
        item = ASSETS.get(self.path)
        if item is None:
            self._json(404, {"error": "NOT_FOUND"})
            return
        name, kind = item
        path = HERE / name
        if path.is_symlink() or not path.is_file():
            self._json(503, {"error": "UNSAFE_OR_MISSING_RESOURCE"})
            return
        data = path.read_bytes()
        self._respond(200, data, kind)

    def do_POST(self):
        if not self._allowed_host() or not self._valid_origin():
            self._json(403, {"error": "SAME_ORIGIN_REQUIRED"})
            return
        if self.path != "/api/analyze":
            self._json(404, {"error": "NOT_FOUND"})
            return
        if (self.headers.get_all("Transfer-Encoding", [])
                or len(self.headers.get_all("Content-Length", [])) != 1):
            self._json(400, {"error": "CONTENT_LENGTH_REQUIRED"})
            return
        content_type = self.headers.get_all("Content-Type", [])
        if content_type != ["application/json"]:
            self._json(415, {"error": "JSON_CONTENT_TYPE_REQUIRED"})
            return
        raw_length = self.headers["Content-Length"]
        if not re.fullmatch(r"[0-9]{1,7}", raw_length):
            self._json(413, {"error": "INVALID_SIZE"})
            return
        length = int(raw_length)
        if not 0 < length <= MAX_REQUEST:
            self._json(413, {"error": "INVALID_SIZE"})
            return
        try:
            packet = json.loads(self.rfile.read(length).decode("utf-8"),
                                parse_float=str)
            self._json(200, audit(packet))
        except (ValueError, TypeError, UnicodeDecodeError, KeyError, OverflowError,
                ArithmeticError) as exc:
            self._json(422, {"error": "INVALID_INPUT", "detail": str(exc)[:220]})

    def do_OPTIONS(self):
        self._json(405, {"error": "NO_CROSS_ORIGIN_API"})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8766)
    args = p.parse_args(argv)
    if not 0 <= args.port <= 65535:
        p.error("port outside valid range")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("ASTRA_WATER_PRIVATE_LOCAL_URL=http://127.0.0.1:" +
          str(server.server_address[1]), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
