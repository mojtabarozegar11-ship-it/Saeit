#!/usr/bin/env python3
"""Read-only anonymous public observations. No forms, cookies, secrets or writes."""
from __future__ import annotations
import hashlib
import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path

ORIGIN = "https://zomorodmelal.ir"
ROUTES = ("/", "/company/", "/b2b/", "/b2b/privacy/", "/en/partners/", "/privacy/")
EXPECTED = {
    "/b2b/": "public/b2b/index.html",
    "/b2b/privacy/": "public/b2b/privacy/index.html",
}
LIMIT = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def classify(status, content, reference=None):
    if status != 200:
        return "NOT_HTTP_200"
    if reference is None:
        return "HTTP_200_ONLY"
    return "EXACT_REVIEWED_BYTES" if hashlib.sha256(content).digest() == hashlib.sha256(reference).digest() else "HTTP_200_DIFFERENT_BYTES"

def observe(route, opener, root=ROOT):
    if route not in ROUTES:
        raise ValueError("unapproved route")
    result = {"route": route, "status": None, "classification": "UNKNOWN", "tls_verified": False}
    req = urllib.request.Request(ORIGIN + route, method="GET", headers={
        "User-Agent":"Zomorod-public-release-observation/1.0",
        "Accept-Encoding":"identity",
        "Accept":"text/html",
    })
    try:
        with opener.open(req, timeout=8) as res:
            status = res.status
            result.update(status=status, tls_verified=True)
            if res.geturl() != ORIGIN + route:
                result["classification"] = "UNEXPECTED_REDIRECT"
                return result
            body = res.read(LIMIT+1)
            if len(body) > LIMIT:
                result["classification"] = "BODY_TOO_LARGE"
                return result
            result["sha256"] = hashlib.sha256(body).hexdigest()
            if status == 200 and res.headers.get_content_type() != "text/html":
                result["classification"] = "NON_HTML_RESPONSE"
                return result
            reference = (root / EXPECTED[route]).read_bytes() if route in EXPECTED else None
            result["classification"] = classify(status, body, reference)
    except urllib.error.HTTPError as exc:
        result.update(status=exc.code, tls_verified=True, classification="HTTP_ERROR_OR_REDIRECT")
        exc.close()
    except (OSError, ValueError, urllib.error.URLError):
        result["classification"] = "TRANSPORT_OR_LOCAL_ERROR"
    return result

def main():
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        NoRedirect(),
    )
    results = [observe(route, opener) for route in ROUTES]
    print(json.dumps({"schema":"zomorod.public.readonly.v1","observations":results,
                      "site_changed":False,"form_submitted":False,
                      "commercial_readiness_proven":False}, sort_keys=True))

if __name__ == "__main__":
    main()
