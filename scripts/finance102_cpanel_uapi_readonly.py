#!/usr/bin/env python3
"""Owner-manual read-only cPanel UAPI app mapping through TLS on port 2083.

No SSH, no file changes, no backup/delete/upload actions or remote execution.
Requires FINANCE102_CPANEL_API_TOKEN in secret environment; never prints token.
"""
import json
import os
import ssl
import urllib.error
import urllib.request

HOST = "zohal.pws-dns.net"
API_PATH = "/execute/PassengerApps/list_applications"
API_URL = "https://" + HOST + ":2083" + API_PATH
USER = "zomorod2"
EXPECTED = (
    ("zomorodmelal.ir", "/", "/home/zomorod2/Saeit"),
    ("mojplaywin.com", "/", "/home/zomorod2/Saeit-staging"),
)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("CPANEL_REDIRECT_NOT_AUTHORIZED")

def classify(result):
    """Do not leak server metadata; accept at most one exact mapping per site."""
    if not isinstance(result, dict) or set(result) != {"data", "errors", "messages", "metadata", "status"}:
        # cPanel UAPI returns a dictionary with these keys on supported versions.
        # Never classify an unexpected shape as authenticated proof.
        raise ValueError("CPANEL_RESPONSE_SHAPE_UNVERIFIED")
    if result["status"] not in (1, True) or result["errors"]:
        raise ValueError("CPANEL_UAPI_NOT_AUTHENTICATED_OR_DENIED")
    stack = [result["data"]]
    found = []
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if all(k in item for k in ("domain", "base_uri", "path")):
                found.append((str(item["domain"]).lower(), str(item["base_uri"]), str(item["path"])))
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return {d: found.count((d, uri, p)) == 1 for d, uri, p in EXPECTED}

def run(token, opener=None):
    if not isinstance(token, str) or not 18 <= len(token) <= 300 or "\n" in token or "\r" in token:
        raise ValueError("CPANEL_TOKEN_NOT_CONFIGURED")
    if opener is None:
        opener = urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
        )
    request = urllib.request.Request(API_URL, method="GET", headers={
        "Authorization": "cpanel " + USER + ":" + token,
        "Accept": "application/json",
        "User-Agent": "Saeit-Finance102-ReadOnly/1.0",
    })
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("CPANEL_NON_JSON_OR_HTTP_ERROR")
            raw = response.read(500_001)
            if len(raw) > 500_000:
                raise ValueError("CPANEL_RESPONSE_TOO_LARGE")
            data = json.loads(raw.decode("utf8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError("CPANEL_HTTPS_UNAVAILABLE_OR_DENIED") from exc
    if not isinstance(data, dict) or "result" not in data:
        raise ValueError("CPANEL_UAPI_NO_RESULT")
    return classify(data["result"])

def main():
    try:
        result = run(os.environ.get("FINANCE102_CPANEL_API_TOKEN"))
        print("FINANCE102_CPANEL_HTTPS_APP_MAPPINGS=" + json.dumps(result, sort_keys=True))
        print("FINANCE102_CPANEL_AUTHENTICATED_READONLY=YES")
        print("FINANCE102_CPANEL_LIVE_FILE_PARITY=NOT_CHECKED")
        print("FINANCE102_REMOTE_WRITES=0")
        return 0 if all(result.values()) else 2
    except ValueError as exc:
        print("FINANCE102_CPANEL_HTTPS_READONLY=" + str(exc))
        print("FINANCE102_REMOTE_WRITES=0")
        return 3

if __name__ == "__main__":
    raise SystemExit(main())
