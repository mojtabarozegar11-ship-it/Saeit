#!/usr/bin/env python3
"""Read-only public HTTP acceptance gate for official MojPlayWin support email.

No SSH, FTP, payment calls, submissions, writes or customer data. Failure is
expected while production still serves the historical support address.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

ORIGIN = "https://mojplaywin.com"
INBOX = "mojplaywin@gmail.com"
LEGACY = "support@mojplaywin.com"
ROUTES = (
    "/",
    "/store/",
    "/contact/",
    "/support/",
    "/about/",
    "/company/",
    "/mpw-editorial/revenue/inquiry.php?service=general",
)
MAX_BYTES = 2_000_000


def _same_public_url(expected: str, actual: str) -> bool:
    a, b = urllib.parse.urlsplit(expected), urllib.parse.urlsplit(actual)
    return (b.scheme == "https" and b.netloc == "mojplaywin.com"
            and a.path == b.path and a.query == b.query)


def fetch_public(url: str) -> str:
    if not url.startswith(ORIGIN + "/") or not any(url == ORIGIN + r for r in ROUTES):
        raise ValueError("NON_ALLOWLISTED_URL")
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache",
                 "User-Agent": "MojPlayWin-Support-ReadOnly-Check/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("NON_200_RESPONSE")
        if not _same_public_url(url, response.geturl()):
            raise RuntimeError("UNEXPECTED_FINAL_URL")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            raise RuntimeError("NON_HTML_RESPONSE")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError("RESPONSE_TOO_LARGE")
    return raw.decode("utf-8", errors="replace")


def assess(fetcher: Callable[[str], str] = fetch_public) -> dict:
    results = []
    for path in ROUTES:
        try:
            html = fetcher(ORIGIN + path)
            if not isinstance(html, str):
                raise TypeError("INVALID_RESPONSE_TYPE")
            new = INBOX in html
            old = LEGACY in html
            mailto = "mailto:" + INBOX in html
            label = "READY" if new and mailto and not old else "MISSING_NEW_CONTACT"
            if old:
                label = "LEGACY_CONTACT_VISIBLE"
            if path == "/store/" and "MPW_STATIC_STORE_FALLBACK_V1" in html:
                source = "STATIC_STORE_FALLBACK_VISIBLE"
            elif path == "/store/":
                source = "STATIC_STORE_FALLBACK_NOT_OBSERVED"
            else:
                source = "NOT_APPLICABLE"
            results.append({"route": path, "status": label, "email_visible": new,
                            "mailto_visible": mailto, "legacy_visible": old,
                            "store_source_indicator": source})
        except (OSError, RuntimeError, ValueError, TypeError, UnicodeError) as exc:
            results.append({"route": path, "status": "FETCH_FAILED",
                            "error_class": type(exc).__name__,
                            "email_visible": False, "mailto_visible": False,
                            "legacy_visible": False,
                            "store_source_indicator": "UNKNOWN"})
    passed = sum(x["status"] == "READY" for x in results)
    return {
        "contract": "MOJPLAYWIN_OFFICIAL_SUPPORT_LIVE_GATE_V1",
        "mode": "PUBLIC_READ_ONLY_GET",
        "required_routes": len(ROUTES),
        "ready_routes": passed,
        "support_ready": passed == len(ROUTES),
        "live_release_confirmed": passed == len(ROUTES),
        "production_files_modified": False,
        "emails_sent": False,
        "payments_attempted": False,
        "observations": results,
    }


def main() -> int:
    report = assess()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["support_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
