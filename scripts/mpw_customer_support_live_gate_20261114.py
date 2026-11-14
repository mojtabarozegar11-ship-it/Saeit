#!/usr/bin/env python3
"""Read-only public HTTP acceptance gate for official MojPlayWin support email.

No SSH, FTP, payment calls, submissions, writes or customer data. Failure is
expected while production still serves the historical support address.
"""
from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
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
# Three catalog products confirmed in the owned static store generator.
STORE_PRODUCT_IDS = ("72", "225", "879")

# Reject generic 200-OK placeholders that happen to contain the support email.
# These route markers reflect the existing public pages.
ROUTE_IDENTITY = {
    "/": ("MojPlayWin", "digital"),
    "/store/": ("The Science and Practice of Chess Improvement",
                "/store/product/72/", "Guest checkout with TRX"),
    "/contact/": ("MojPlayWin", "business"),
    "/support/": ("support", "order"),
    "/about/": ("MojPlayWin", "research"),
    "/company/": ("MojPlayWin", "company"),
    "/mpw-editorial/revenue/inquiry.php?service=general":
        ("General MojPlayWin Business Inquiry", "No payment"),
}



class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect before verifying the final URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("UNEXPECTED_REDIRECT")


class _SupportMailtoLinks(HTMLParser):
    """Look for an actual customer-facing mailto anchor, not source text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = False
        self._ignored = 0
        self._base_tag_seen = False
        self._anchor_hrefs = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style", "template"):
            self._ignored += 1
            return
        if self._ignored:
            return
        if tag == "base":
            # An HTML base tag can silently redirect otherwise-local links.
            self._base_tag_seen = True
            return
        if tag != "a":
            return
        hrefs = [value for key, value in attrs if key.lower() == "href"]
        if len(hrefs) != 1 or not isinstance(hrefs[0], str):
            return
        self._anchor_hrefs.append(hrefs[0])
        address = hrefs[0].split("?", 1)[0]
        if address.lower() == "mailto:" + INBOX:
            self.found = True

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "template") and self._ignored:
            self._ignored -= 1


def _scan_anchors(html: str) -> _SupportMailtoLinks:
    parser = _SupportMailtoLinks()
    parser.feed(html)
    parser.close()
    return parser


def _has_support_mailto(html: str) -> bool:
    return _scan_anchors(html).found


def _store_catalog_links_verified(anchors: _SupportMailtoLinks) -> bool:
    if anchors._base_tag_seen:
        return False
    hrefs = set(anchors._anchor_hrefs)
    # Exact same-origin HTML anchors, not text snippets, JavaScript hrefs,
    # external domains or auto-resolving relative paths under an HTML base tag.
    return all(
        any(
            target in hrefs
            for target in (
                f"/store/product/{product_id}/",
                f"/store/product/{product_id}/checkout/",
                ORIGIN + f"/store/product/{product_id}/",
                ORIGIN + f"/store/product/{product_id}/checkout/",
            )
        )
        for product_id in STORE_PRODUCT_IDS
    )


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
    with urllib.request.build_opener(_RejectRedirects()).open(req, timeout=15) as response:
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
            anchors = _scan_anchors(html)
            mailto = anchors.found
            catalog_links = (_store_catalog_links_verified(anchors)
                             if path == "/store/" else None)
            page_identity = (
                all(marker.lower() in html.lower() for marker in ROUTE_IDENTITY[path])
                and (catalog_links if path == "/store/" else True)
            )
            label = "READY" if new and mailto and not old and page_identity else "MISSING_NEW_CONTACT"
            if new and mailto and not page_identity:
                label = "UNRECOGNIZED_PAGE"
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
                            "page_identity_verified": page_identity,
                            "store_product_links_verified": catalog_links,
                            "store_source_indicator": source})
        except (OSError, RuntimeError, ValueError, TypeError, UnicodeError) as exc:
            results.append({"route": path, "status": "FETCH_FAILED",
                            "error_class": type(exc).__name__,
                            "email_visible": False, "mailto_visible": False,
                            "legacy_visible": False,
                            "page_identity_verified": False,
                            "store_product_links_verified": False if path == "/store/" else None,
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
