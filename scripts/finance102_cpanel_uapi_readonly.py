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
    required = {"data", "errors", "messages", "metadata", "status"}
    # UAPI can add "warnings" and minor metadata in legitimate releases.
    if not isinstance(result, dict) or not required.issubset(result):
        raise ValueError("CPANEL_RESPONSE_SHAPE_UNVERIFIED")
    if result["status"] not in (1, True) or result["errors"] not in (None, []):
        raise ValueError("CPANEL_UAPI_NOT_AUTHENTICATED_OR_DENIED")
    if not isinstance(result["data"], (list, dict)):
        raise ValueError("CPANEL_APPLICATION_DATA_UNVERIFIED")
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


def parse_uapi_response(data):
    """Support exactly the two documented UAPI JSON wire envelopes.

    Direct /execute/ replies expose data/status at the root. Some versions
    document the API-v3 module/function envelope; accept that only when the
    operation identity is explicitly verified. Never trust a bare result key.
    """
    if not isinstance(data, dict):
        raise ValueError("CPANEL_UAPI_JSON_SHAPE_UNVERIFIED")
    if "result" not in data:
        return classify(data)
    if not (data.get("apiversion") == 3
            and data.get("module") == "PassengerApps"
            and data.get("func") == "list_applications"):
        raise ValueError("CPANEL_UAPI_OPERATION_IDENTITY_UNVERIFIED")
    return classify(data["result"])

def run(token, opener=None, identity_preflight=None):
    if not isinstance(token, str) or not 18 <= len(token) <= 300 or "\n" in token or "\r" in token:
        raise ValueError("CPANEL_TOKEN_NOT_CONFIGURED")
    # A credential must never be sent to an unresolved or mismatched host.
    # The production call always executes the fixed DNS + CA/SNI TLS preflight.
    # Tests inject an isolated fake, never a bypass from a public command flag.
    if identity_preflight is None:
        from scripts.finance102_cpanel_tls_preflight import check as identity_preflight
    identity = identity_preflight()
    if not (isinstance(identity, dict)
            and identity.get("dns_exact_expected_ipv4") is True
            and identity.get("tls_hostname_and_ca_verified") is True):
        raise ValueError("CPANEL_DESTINATION_IDENTITY_UNVERIFIED")
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
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("CPANEL_INVALID_JSON_RESPONSE") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError("CPANEL_HTTPS_UNAVAILABLE_OR_DENIED") from exc
    return parse_uapi_response(data)

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
