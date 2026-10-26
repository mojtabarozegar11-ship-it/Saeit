#!/usr/bin/env python3
"""Read-only HTTP continuity check for MojPlayWin and its protected child sites.

The real sub-sites are URL prefixes beneath mojplaywin.com, not unverified
hostnames such as taniya.mojplaywin.com. Only GET is used: /farnaz/ and
/picm/ intentionally do not support HEAD.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from html.parser import HTMLParser


ORIGIN = "https://mojplaywin.com"
# The owner's standalone personal web must be monitored but never modified by
# a change scoped to the main site or the sibling game/commerce web apps.
PERSONAL_PATHS = (
    "/mojtaba.roozegar/",
    "/mojtaba.roozegar/about/",
    "/mojtaba.roozegar/resume/",
    "/mojtaba.roozegar/works-activities/",
    "/mojtaba.roozegar/memories/",
    "/mojtaba.roozegar/stories/",
    "/mojtaba.roozegar/blog/",
    "/mojtaba.roozegar/contact/",
    "/mojtaba.roozegar/gallery/",
    "/mojtaba.roozegar/projects/",
    "/mojtaba.roozegar/privacy/",
)
REQUIRED_PATHS = (
    "/",
    "/store/",
    "/store/product/72/",
    "/store/product/225/",
    "/store/product/879/",
    "/games/",
    "/knowledge/",
    "/research/",
    "/company/",
    "/ventures/agriculture/",
    "/farnaz/",
    "/saman/",
    "/taniya/",
    "/picm/",
) + PERSONAL_PATHS
PROTECTED_CHILDREN = ("/farnaz/", "/saman/", "/taniya/", "/picm/")
SITEMAP_URLS = (
    "/knowledge/",
    "/research/",
    "/company/",
    "/taniya/",
    "/ventures/agriculture/",
)
PROTECTED_PRODUCT_IDS = (72, 225, 879)


class BasicHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.saw_html = False
        self.saw_body = False
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "html":
            self.saw_html = True
        elif tag == "body":
            self.saw_body = True
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data.strip()


@dataclass
class Check:
    target: str
    effective: str
    status: int
    seconds: float
    title: str = ""


def get(url: str, *, max_bytes: int = 950000, attempts: int = 3) -> tuple[Check, bytes]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        start = time.monotonic()
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "MojPlayWin-ReadOnly-Continuity/1.0",
                    "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
                    "Cache-Control": "no-cache",
                },
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=22) as response:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError("Response exceeded bounded inspection size")
                return (
                    Check(url, response.geturl(), response.status,
                          round(time.monotonic() - start, 2)),
                    data,
                )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failure for {url}: {last_error}")


def check_site_page(path: str) -> Check:
    check, data = get(ORIGIN + path)
    expected_final = ORIGIN + ("/picm/login/" if path == "/picm/" else path)
    parsed_final = urllib.parse.urlsplit(check.effective)
    # Optional query params added by the application are allowed. A route that
    # silently resolves to / or to an unrelated app is not considered healthy.
    actual_final = urllib.parse.urlunsplit((parsed_final.scheme, parsed_final.netloc,
                                           parsed_final.path, "", ""))
    if check.status != 200 or actual_final != expected_final:
        raise RuntimeError(f"Wrong result for {path}: {check.status}, {check.effective}")
    if len(data) < 150:
        raise RuntimeError(f"Empty or incomplete HTML page at {path}")
    document = BasicHtml()
    document.feed(data.decode("utf-8", "replace"))
    if not document.saw_html or not document.saw_body:
        raise RuntimeError(f"HTML document missing for {path}")
    if path == "/" and b'data-mpw-structure-v1="20261026"' not in data:
        raise RuntimeError("Approved homepage structure marker is absent")
    if path.startswith("/mojtaba.roozegar/"):
        if b"mojtaba.roozegar/" not in data or "Mojtaba" not in document.title:
            raise RuntimeError(f"Personal website identity/structure changed at {path}")
        if path == PERSONAL_PATHS[0] and (
            b'id="mpw-social-central-hub-20261026"' not in data
            or b'id="mpw-primary-personal-profile-20261016"' not in data
        ):
            raise RuntimeError("Personal website home identity/hub no longer matches baseline")
    check.title = document.title[:150]
    return check


def check_sitemap() -> tuple[Check, int]:
    check, data = get(ORIGIN + "/sitemap.xml", max_bytes=2000000)
    if check.status != 200:
        raise RuntimeError("Sitemap is not accessible")
    root = ET.fromstring(data)
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls = [item.text for item in root.iter(namespace + "loc")]
    if len(urls) < 69 or len(urls) != len(set(urls)):
        raise RuntimeError(f"Sitemap URLs are missing or duplicated: {len(urls)}")
    for path in SITEMAP_URLS:
        if urls.count(ORIGIN + path) != 1:
            raise RuntimeError(f"Missing sitemap URL: {path}")
    for url in urls:
        if not url or not url.startswith(ORIGIN + "/"):
            raise RuntimeError(f"Untrusted sitemap origin: {url}")
    return check, len(urls)


def check_authentication_gate(product_id: int) -> Check:
    path = f"/store/product/{product_id}/checkout/"
    check, _ = get(ORIGIN + path)
    landing = urllib.parse.urlsplit(check.effective)
    if check.status != 200 or landing.scheme != "https" or landing.netloc != "mojplaywin.com":
        raise RuntimeError(f"Checkout {product_id} resolved outside store: {check.effective}")
    if landing.path != "/accounts/login/":
        raise RuntimeError(f"Checkout {product_id} bypassed login: {check.effective}")
    return check


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        assert len(PROTECTED_CHILDREN) == 4
        assert len(PERSONAL_PATHS) == 11
        assert PERSONAL_PATHS[0] in REQUIRED_PATHS
        assert "/picm/" in REQUIRED_PATHS
        assert len(set(REQUIRED_PATHS)) == len(REQUIRED_PATHS)
        assert all(path.startswith("/") for path in REQUIRED_PATHS)
        print("READ_ONLY_CONTINUITY_SELFTEST_OK")
        return 0

    checks = [check_site_page(path) for path in REQUIRED_PATHS]
    sitemap, sitemap_count = check_sitemap()
    auth_checks = [check_authentication_gate(pk) for pk in PROTECTED_PRODUCT_IDS]
    results = {
        "main_and_child_pages": [asdict(check) for check in checks],
        "sitemap": {**asdict(sitemap), "unique_urls": sitemap_count},
        "anonymous_checkout_gates": [asdict(check) for check in auth_checks],
        "protected_children": list(PROTECTED_CHILDREN),
        "protected_personal_site": list(PERSONAL_PATHS),
        "read_only": True,
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write("## MojPlayWin protected subsite continuity\n\n")
            summary.write(f"- Main and child GET pages: {len(checks)} passed\n")
            summary.write(f"- Protected child apps: {', '.join(PROTECTED_CHILDREN)}\n")
            summary.write(f"- Owner's personal website: {len(PERSONAL_PATHS)} pages unchanged and accessible\n")
            summary.write(f"- Unique sitemap entries: {sitemap_count}\n")
            summary.write("- Anonymous product checkout guards: 3 passed\n")
            summary.write("- Server mutations: none\n")
    print("MPW_MAIN_AND_PROTECTED_CHILDREN_ALL_HEALTHY")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ET.ParseError) as failure:
        print(f"MPW_PROTECTED_SUBSITE_CONTINUITY_FAILED: {failure}", file=sys.stderr)
        sys.exit(1)
