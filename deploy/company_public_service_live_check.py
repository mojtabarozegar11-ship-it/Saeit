#!/usr/bin/env python3
"""Public GET-only proof for six scoped Zomorod service offers; no PII or POST."""
from __future__ import annotations

import ssl
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler

BASE = "https://zomorodmelal.ir"
CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")
LIMIT = 96 * 1024

class NoFollow(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def check(path: str, marker: str) -> dict:
    if not path.startswith("/") or any(x in path for x in ("..", "?", "#", "//")):
        raise ValueError("unsafe fixed public path")
    url = BASE + path
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoFollow)
    request = Request(url, headers={"User-Agent": "ZM-Service-Visibility/1", "Cache-Control": "no-cache"})
    status = "UNKNOWN"
    marker_verified = False
    reason = "UNKNOWN"
    try:
        with opener.open(request, timeout=13) as response:
            status = str(response.status)
            content_type = response.headers.get("Content-Type", "").lower()
            if response.status == 200 and "text/html" in content_type:
                body = response.read(LIMIT + 1)
                if len(body) > LIMIT:
                    reason = "TRUNCATED"
                else:
                    page = body.decode("utf-8", errors="replace")
                    marker_verified = marker in page
                    reason = "MARKER_SEEN" if marker_verified else "MARKER_MISSING"
            else:
                reason = "NOT_HTML_200"
    except HTTPError as exc:
        status = str(exc.code)
        reason = "NON_200_OR_REDIRECT"
    except (URLError, TimeoutError, OSError):
        reason = "NETWORK_OR_TLS_UNAVAILABLE"
    return {"status": status, "marker": marker_verified, "reason": reason}

def main() -> None:
    print("ZM_SERVICE_PUBLIC_READ_ONLY=true")
    complete = 0
    for code in CODES:
        res = check("/services/scope/" + code + "/", "scope-primary-cta")
        ready = res["status"] == "200" and res["marker"]
        if ready:
            complete += 1
        print(f"ZM_SERVICE_{code.replace('-', '_')}_HTTP={res['status']}")
        print(f"ZM_SERVICE_{code.replace('-', '_')}_PROVEN_PUBLIC={str(ready).lower()}")
        print(f"ZM_SERVICE_{code.replace('-', '_')}_REASON={res['reason']}")
    index = check("/services/", 'id="service-offers-heading"')
    print("ZM_SERVICES_INDEX_HTTP=" + index["status"])
    print("ZM_SERVICES_INDEX_HAS_SIX_OFFER_SECTION=" + str(index["marker"]).lower())
    print(f"ZM_SCOPE_PAGES_VERIFIED_PUBLIC={complete}/{len(CODES)}")
    print("ZM_ORDERS_OR_SETTLEMENTS_VERIFIED=unknown")
    print("ZM_EXTERNAL_POSTS_SENT=0")

if __name__ == "__main__":
    main()
