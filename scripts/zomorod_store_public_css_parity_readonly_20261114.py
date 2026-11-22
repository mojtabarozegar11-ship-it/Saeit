#!/usr/bin/env python3
"""GET-only comparison: current public Zomorod store CSS vs existing GitHub PHP.

No authentication, cookies, form submissions, server writes, PHP execution,
financial transactions, or private host access. A matching public CSS signature
does NOT prove deployed-file identity, paid sales, or browser acceptance.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

URL = "https://zomorodmelal.ir/store/"
MAX_BYTES = 1_500_000
CSS_RULE = ".grid article small.muted{display:block;max-width:100%;overflow-wrap:anywhere;word-break:break-word}"
GRID_RULE = "grid-template-columns:repeat(auto-fit,minmax(min(100%,255px),1fr))"
PHP_SOURCE = Path(__file__).resolve().parents[1] / "content/zomorod-v11/store_index.php"


class StyleReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside_style = False
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "style":
            self.inside_style = True

    def handle_endtag(self, tag):
        if tag.lower() == "style":
            self.inside_style = False

    def handle_data(self, data):
        if self.inside_style:
            self.fragments.append(data)


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
            raise ValueError("unexpected_redirect_host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def compare(source: str, html: str, status: int = 200, final_url: str = URL,
            content_type: str = "text/html") -> dict:
    u = urlsplit(final_url)
    if u.scheme != "https" or u.hostname not in ("zomorodmelal.ir", "www.zomorodmelal.ir"):
        raise ValueError("unexpected_final_host")
    if status != 200:
        raise ValueError("public_store_non_200")
    if "text/html" not in content_type.lower():
        raise ValueError("public_store_non_html")
    if CSS_RULE not in source or GRID_RULE not in source:
        raise ValueError("expected_source_css_missing")
    p = StyleReader()
    p.feed(html)
    p.close()
    styles = "\n".join(p.fragments)
    css_present = CSS_RULE in styles
    grid_present = GRID_RULE in styles
    return {
        "scope": "public_html_get_only",
        "source_css_rule_present": True,
        "source_grid_rule_present": True,
        "public_css_rule_present": css_present,
        "public_grid_rule_present": grid_present,
        "public_parity_for_two_css_markers": bool(css_present and grid_present),
        "public_html_sha256": hashlib.sha256(html.encode("utf8")).hexdigest(),
        "public_html_bytes": len(html.encode("utf8")),
        "browser_overflow_verified_by_this_check": False,
        "cpanel_active_file_hash_verified": False,
        "site_writes": 0,
        "forms_submitted": 0,
        "payments": 0,
        "release_gate": "blocked_pending_exact_cpanel_source_and_authorized_deploy",
    }


def main():
    source = PHP_SOURCE.read_text(encoding="utf8")
    opener = build_opener(SameHostRedirect())
    request = Request(URL, headers={
        "User-Agent": "ZomorodPublicCssParity/1.0 (read-only)",
        "Accept": "text/html",
        "Cache-Control": "no-cache",
    }, method="GET")
    with opener.open(request, timeout=22) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("public_html_exceeds_bounded_limit")
        result = compare(
            source, body.decode("utf8", "replace"), response.status,
            response.url, response.headers.get("Content-Type", ""),
        )
    print("ZM_PUBLIC_STORE_CSS_PARITY=" + json.dumps(result, ensure_ascii=False), flush=True)
    runner_temp = os.environ.get("RUNNER_TEMP")
    if runner_temp:
        dest = Path(runner_temp) / "zomorod-public-store-css-parity.json"
        dest.write_text(json.dumps(result, indent=2), encoding="utf8")
        print("ZM_PUBLIC_STORE_PARITY_REPORT_WRITTEN=yes", flush=True)


if __name__ == "__main__":
    main()
