"""Small auditable HTTP adapter. Suppresses URL/token contents from errors."""
from __future__ import annotations
import json
import urllib.error
import urllib.request

from .adapters import Response, Uncertain

MAX_JSON_BYTES = 2_000_000

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Uncertain("Unexpected external API redirect; refuse token forwarding")

_OPENER = urllib.request.build_opener(_NoRedirect)

def http_transport(method: str, url: str, body, headers: dict) -> Response:
    """Use only URLs constructed by adapters, never unsanitized user-supplied URLs."""
    if method not in ("POST", "PUT", "GET"):
        raise Uncertain("Unrecognized HTTP method")
    if isinstance(body, dict):
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    elif isinstance(body, str):
        encoded = body.encode("utf-8")
    elif isinstance(body, bytes):
        encoded = body
    elif body is None:
        encoded = None
    else:
        raise Uncertain("Invalid HTTP body")
    request = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        with _OPENER.open(request, timeout=30) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
            if len(raw) > MAX_JSON_BYTES:
                raise Uncertain("Upstream response too large")
            mime = response.headers.get("Content-Type", "")
            if raw and ("json" in mime or raw[:1] in (b"{", b"[")):
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise Uncertain("Invalid upstream JSON") from None
                if not isinstance(payload, dict):
                    raise Uncertain("Unexpected remote object")
            else:
                payload = {}
            return Response(response.status, payload, dict(response.headers))
    except urllib.error.HTTPError as exc:
        # Resumable YouTube upload HTTP 308 is a normal in-progress response.
        if exc.code == 308:
            return Response(308, {}, dict(exc.headers))
        raise Uncertain("Remote HTTP failure " + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Uncertain("Remote outcome unknown; do not auto-retry") from None
