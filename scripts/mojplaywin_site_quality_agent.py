#!/usr/bin/env python3
"""Read-only MojPlayWin main-site quality agent.

No credentials, no Django database, no payments, no publishing or server restart.
Only whitelisted public URLs on mojplaywin.com are requested with GET.
No requests are made to /mojtaba.roozegar/ or any independent subsite.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "mojplaywin.com"
ROUTES = (
    "/", "/store/", "/research/", "/studio/", "/agents/", "/market/",
    "/company/", "/games/", "/ai/", "/blockchain/", "/products/",
    "/crypto-payments/", "/global-business/", "/support/", "/research-lab/",
    "/ventures/agriculture/", "/ventures/cafe-restaurant/",
    "/ventures/fuel-station/", "/ventures/jewelry-gold/", "/ventures/carpets/",
    "/ventures/currency-crypto/", "/ventures/ecommerce/",
    "/ventures/hospitality/",
)


class HostGuardRedirect(HTTPRedirectHandler):
    """Never follow a redirect outside the sole approved host."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if parsed.scheme != "https" or parsed.hostname != HOST:
            raise URLError("out_of_scope_redirect")
        if parsed.path not in ROUTES:
            raise URLError("out_of_scope_path")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class PageAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.canonical = ""
        self.h1 = 0
        self.main_depth = 0
        self.text_chunks = []
        self.images = []
        self._inside_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._inside_title = True
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "main":
            self.main_depth += 1
        if self.main_depth:
            if tag == "h1":
                self.h1 += 1
            if tag == "img":
                self.images.append({
                    "src": attrs.get("src", ""),
                    "alt": attrs.get("alt", ""),
                    "alt_present": "alt" in attrs,
                })

    def handle_endtag(self, tag):
        if tag == "title":
            self._inside_title = False
        if tag == "main":
            self.main_depth = max(0, self.main_depth - 1)

    def handle_data(self, data):
        if self._inside_title:
            self.title += data
        if self.main_depth and data.strip():
            self.text_chunks.append(data.strip())


def get_public_html(url: str, timeout: int = 12):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.path not in ROUTES:
        raise ValueError("out_of_scope_url")
    req = Request(url, headers={"User-Agent": "MojPlayWin-ReadOnly-Quality-Agent/1.0"})
    opener = build_opener(HostGuardRedirect())
    with opener.open(req, timeout=timeout) as response:
        status = response.getcode()
        payload = response.read(1_500_000).decode("utf-8", errors="replace")
    return status, payload


def inspect_page(path: str, fetch=get_public_html) -> dict:
    if path not in ROUTES:
        raise ValueError("out_of_scope_path")
    url = "https://" + HOST + path
    result = {"path": path, "url": url, "ok": False, "issues": []}
    try:
        status, html = fetch(url)
        parser = PageAudit()
        parser.feed(html)
        word_count = len(" ".join(parser.text_chunks).split())
        images = parser.images
        result.update({"http_status": status, "title": parser.title.strip(),
                       "canonical": parser.canonical, "h1_count": parser.h1,
                       "main_words": word_count, "main_images": len(images)})
        if status != 200:
            result["issues"].append("http_not_200")
        if not parser.title.strip():
            result["issues"].append("missing_title")
        if parser.canonical != url:
            result["issues"].append("wrong_canonical")
        if parser.h1 != 1:
            result["issues"].append("h1_count_not_one")
        if word_count < (140 if path != "/" else 230):
            result["issues"].append("thin_main_content")
        if len(images) < (3 if path.startswith("/ventures/") or path in ("/agents/", "/research/", "/studio/", "/market/", "/company/") else 1):
            result["issues"].append("insufficient_images")
        if any(not img["src"] or not img["alt_present"] for img in images):
            result["issues"].append("image_missing_src_or_alt_attribute")
    except (URLError, HTTPError, ValueError, TimeoutError, OSError) as exc:
        result["issues"].append(type(exc).__name__ + ":" + str(exc)[:100])
    result["ok"] = not result["issues"]
    return result


def run(fetch=get_public_html):
    pages = [inspect_page(path, fetch=fetch) for path in ROUTES]
    return {
        "scope": "mojplaywin.com main domain only",
        "mode": "read_only",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "pages_checked": len(pages),
        "pages_passed": sum(p["ok"] for p in pages),
        "pages": pages,
        "actions_taken": ["HTTP GET on explicitly whitelisted public main-site URLs"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("mojplaywin-quality-report.json"))
    parser.add_argument("--fail-on-issues", action="store_true")
    opts = parser.parse_args()
    report = run()
    opts.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MOJPLAYWIN_READ_ONLY pages={report['pages_checked']} passed={report['pages_passed']} report={opts.output}")
    if opts.fail_on_issues and report["pages_passed"] != report["pages_checked"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
