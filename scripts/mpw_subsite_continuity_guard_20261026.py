#!/usr/bin/env python3
"""Read-only HTTP continuity check for MojPlayWin and its protected child sites.

The real sub-sites are URL prefixes beneath mojplaywin.com, not unverified
hostnames such as taniya.mojplaywin.com. Only GET is used. PICM was
explicitly retired: its public route must stay HTTP 404.
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
    "/studio.Roham/",
    "/zahra$$/",
) + PERSONAL_PATHS
RETIRED_PATHS = ("/picm/",)
PROTECTED_CHILDREN = ("/farnaz/", "/saman/", "/taniya/", "/studio.Roham/", "/zahra$$/")
SITEMAP_URLS = (
    "/knowledge/",
    "/research/",
    "/company/",
    "/taniya/",
    "/ventures/agriculture/",
)
PROTECTED_PRODUCT_IDS = (72, 225, 879)
CHECKOUT_PATHS = frozenset(f"/store/product/{pk}/checkout/" for pk in PROTECTED_PRODUCT_IDS)
# Checkout must be anonymous. Only exact public pages may be reached by redirect.
# Never follow a redirect to an unknown app,
# a different host, or an HTTP URL during a read-only audit.
REDIRECT_PATHS = frozenset(REQUIRED_PATHS) | frozenset(RETIRED_PATHS) | frozenset({
    "/sitemap.xml",
    *CHECKOUT_PATHS,
})


class UnsafeRedirect(RuntimeError):
    pass


class ScopedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.hops = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            target = urllib.parse.urlsplit(newurl)
            query_safe = not target.query
            allowed = (
                target.scheme == "https"
                and target.hostname == "mojplaywin.com"
                and target.port in (None, 443)
                and target.username is None
                and target.password is None
                and target.path in REDIRECT_PATHS
                and query_safe
                and not target.fragment
            )
        except ValueError:
            allowed = False
        if not allowed:
            raise UnsafeRedirect("Redirect outside exact public MojPlayWin scope")
        self.hops += 1
        if self.hops > 3:
            raise UnsafeRedirect("Too many public route redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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


class GuestCheckoutHtml(HTMLParser):
    """Validate the real email-only TRX invoice form on the checkout page."""

    def __init__(self, product_id: int) -> None:
        super().__init__(convert_charrefs=True)
        self.expected_action = f"/commerce/trx-easy/start/{product_id}/"
        self.in_expected_form = False
        self.has_email = False
        self.has_csrf = False
        self.has_submit = False
        self.saw_valid_form = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        fields = dict(attrs)
        if tag == "form":
            self.in_expected_form = (
                fields.get("action") == self.expected_action
                and (fields.get("method") or "").lower() == "post"
            )
            self.has_email = self.has_csrf = self.has_submit = False
        elif self.in_expected_form and tag == "input":
            if (fields.get("name") == "email"
                    and (fields.get("type") or "").lower() == "email"
                    and "required" in fields):
                self.has_email = True
            if (fields.get("name") == "csrfmiddlewaretoken"
                    and (fields.get("type") or "").lower() == "hidden"):
                self.has_csrf = True
        elif self.in_expected_form and tag == "button":
            if (fields.get("type") or "submit").lower() == "submit":
                self.has_submit = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            if (self.in_expected_form and self.has_email
                    and self.has_csrf and self.has_submit):
                self.saw_valid_form = True
            self.in_expected_form = False


@dataclass
class Check:
    target: str
    effective: str
    status: int
    seconds: float
    title: str = ""


def _approved_direct_get(url: str) -> bool:
    """Reject accidental out-of-scope initial requests before opening a socket."""
    try:
        parsed = urllib.parse.urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "mojplaywin.com"
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path in REDIRECT_PATHS
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def get(url: str, *, max_bytes: int = 950000, attempts: int = 3,
        allow_retired_404: bool = False) -> tuple[Check, bytes]:
    if not _approved_direct_get(url):
        raise UnsafeRedirect("Direct GET outside exact public MojPlayWin scope")
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
            # urllib.request.urlopen silently follows arbitrary redirects; a
            # scoped opener prevents cross-host requests and HTTP downgrades.
            opener = urllib.request.build_opener(ScopedRedirect())
            with opener.open(request, timeout=22) as response:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError("Response exceeded bounded inspection size")
                return (
                    Check(url, response.geturl(), response.status,
                          round(time.monotonic() - start, 2)),
                    data,
                )
        except urllib.error.HTTPError as error:
            if (allow_retired_404 and url == ORIGIN + "/picm/" and
                    error.code == 404 and error.geturl() == url):
                return (Check(url, url, 404, round(time.monotonic() - start, 2)), b"")
            last_error = error
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failure for {url}: {last_error}")


def check_site_page(path: str) -> Check:
    check, data = get(ORIGIN + path)
    expected_final = ORIGIN + path
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


def check_retired_picm() -> Check:
    """Only the explicitly retired PICM route may yield HTTP 404."""
    check, _ = get(ORIGIN + "/picm/", allow_retired_404=True)
    if check.status != 404 or check.effective != ORIGIN + "/picm/":
        raise RuntimeError("Retired PICM unexpectedly became publicly accessible")
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
        try:
            parsed = urllib.parse.urlsplit(url)
            trusted = (
                parsed.scheme == "https"
                and parsed.hostname == "mojplaywin.com"
                and parsed.port in (None, 443)
                and parsed.username is None
                and parsed.password is None
                and parsed.path.startswith("/")
                and not parsed.path.startswith("//")
                and not parsed.fragment
                and url == url.strip()
                and not any(char in url for char in (chr(13), chr(10), chr(9)))
            )
        except ValueError:
            trusted = False
        if not trusted:
            raise RuntimeError("Malformed or unsafe sitemap URL")
    return check, len(urls)


def check_guest_checkout(product_id: int) -> Check:
    """Read-only proof of guest checkout; no email, order or payment is submitted."""
    url = ORIGIN + f"/store/product/{product_id}/checkout/"
    check, data = get(url)
    if check.status != 200 or check.effective != url:
        raise RuntimeError(f"Guest checkout {product_id} did not stay on its public URL: {check.effective}")
    document = BasicHtml()
    document.feed(data.decode("utf-8", "replace"))
    form = GuestCheckoutHtml(product_id)
    form.feed(data.decode("utf-8", "replace"))
    if not document.saw_html or not document.saw_body or not form.saw_valid_form:
        raise RuntimeError(f"Guest checkout {product_id} has no valid email-only TRX invoice form")
    check.title = document.title[:150]
    return check

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        assert len(PROTECTED_CHILDREN) == 5
        assert set(PROTECTED_CHILDREN).issubset(REQUIRED_PATHS)
        assert {"/studio.Roham/", "/zahra$$/"}.issubset(REQUIRED_PATHS)
        assert len(PERSONAL_PATHS) == 11
        assert PERSONAL_PATHS[0] in REQUIRED_PATHS
        assert "/picm/" not in REQUIRED_PATHS
        assert RETIRED_PATHS == ("/picm/",)
        assert _approved_direct_get(ORIGIN + "/picm/")
        assert not _approved_direct_get(ORIGIN + "/picm/login/")
        assert "/accounts/login/" not in REDIRECT_PATHS
        assert len(set(REQUIRED_PATHS)) == len(REQUIRED_PATHS)
        assert all(path.startswith("/") for path in REQUIRED_PATHS)
        print("READ_ONLY_CONTINUITY_SELFTEST_OK")
        return 0

    checks = [check_site_page(path) for path in REQUIRED_PATHS]
    retired_picm = check_retired_picm()
    sitemap, sitemap_count = check_sitemap()
    guest_checks = [check_guest_checkout(pk) for pk in PROTECTED_PRODUCT_IDS]
    results = {
        "main_and_child_pages": [asdict(check) for check in checks],
        "sitemap": {**asdict(sitemap), "unique_urls": sitemap_count},
        "anonymous_checkout_gates": [asdict(check) for check in guest_checks],
        "protected_children": list(PROTECTED_CHILDREN),
        "retired_picm": asdict(retired_picm),
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
            summary.write("- Retired PICM: expected HTTP 404 confirmed\n")
            summary.write(f"- Owner's personal website: {len(PERSONAL_PATHS)} pages unchanged and accessible\n")
            summary.write(f"- Unique sitemap entries: {sitemap_count}\n")
            summary.write("- Anonymous email-only TRX checkout forms: 3 passed\n")
            summary.write("- Server mutations: none\n")
    print("MPW_MAIN_AND_PROTECTED_CHILDREN_ALL_HEALTHY")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ET.ParseError) as failure:
        print(f"MPW_PROTECTED_SUBSITE_CONTINUITY_FAILED: {failure}", file=sys.stderr)
        sys.exit(1)
