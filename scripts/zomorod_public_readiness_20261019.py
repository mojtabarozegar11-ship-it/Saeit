#!/usr/bin/env python3
"""Public Zomorod read-only GET readiness, no auth, forms or site mutation."""
import json
import ssl
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

HOST = "zomorodmelal.ir"
ROUTES = ("/", "/company/", "/research/", "/knowledge/", "/agriculture/",
          "/store/", "/search/", "/tala/", "/amozeshgah/")
SECURITY_HEADERS = ("strict-transport-security", "content-security-policy",
                    "x-content-type-options", "referrer-policy")


def inspect(path, opener=urlopen):
    if path not in ROUTES:
        raise ValueError("route_not_allowlisted")
    req = Request(
        "https://" + HOST + path,
        headers={"User-Agent": "ZomorodReadOnlyQA/2026", "Cache-Control": "no-cache"},
        method="GET",
    )
    try:
        with opener(req, timeout=18) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname not in (HOST, "www." + HOST):
                return {"path": path, "status": response.getcode(),
                        "ok": False, "error": "cross_origin_redirect"}
            sample = response.read(2048)
            mime = response.headers.get("Content-Type", "")
            return {
                "path": path,
                "status": response.getcode(),
                "ok": response.getcode() == 200 and bool(sample) and "text/html" in mime.lower(),
                "content_type": mime[:80],
                "security_headers_present": {
                    header: bool(response.headers.get(header)) for header in SECURITY_HEADERS
                },
            }
    except HTTPError as exc:
        return {"path": path, "status": exc.code, "ok": False, "error": "http_error"}
    except (URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        return {"path": path, "status": 0, "ok": False, "error": type(exc).__name__}


def main():
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": HOST,
        "read_only": True,
        "pages": [inspect(p) for p in ROUTES],
    }
    report["ok"] = all(row["ok"] for row in report["pages"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
