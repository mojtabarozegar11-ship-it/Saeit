#!/usr/bin/env python3
"""Read-only MojPlayWin image discoverability audit and additive image sitemap.

The live /sitemap.xml is authoritative: never replace it. This command reads
its public landing pages, checks their HTML image references, and can write a
NEW, separate image sitemap after verifying HTTP image responses.

Usage:
  python scripts/mpw_google_images_audit.py --report /tmp/mpw-images.json
  python scripts/mpw_google_images_audit.py --verify-images --workers 3 \
      --image-sitemap /tmp/mpw-image-sitemap.xml \
      --image-inventory /tmp/mpw-image-inventory.json \
      --report /tmp/mpw-images.json

It does not submit to Google, modify the website, or access private purchases.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET


ORIGIN = "https://mojplaywin.com"
SITEMAP = ORIGIN + "/sitemap.xml"
NS_SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
NS_IMAGE = "http://www.google.com/schemas/sitemap-image/1.1"
DENIED = re.compile(
    r"(?:^|/)(?:admin|api|checkout|cart|download|downloads|private|"
    r"orders?|purchases|account|login|logout|wp-admin)(?:/|$)", re.I
)
DENIED_EXTENSION = re.compile(r"\.(?:pdf|zip|rar|7z|tar|gz|exe|db)(?:$|\?)", re.I)
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".bmp"}
SENSITIVE_QUERY = {"token", "secret", "key", "signature", "sig", "auth", "password", "expires"}


def public_url(url: str, *, image: bool = False) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "mojplaywin.com":
        return False
    if parsed.username or parsed.password or DENIED.search(parsed.path) or DENIED_EXTENSION.search(parsed.path):
        return False
    if any(part.split("=", 1)[0].lower() in SENSITIVE_QUERY for part in parsed.query.split("&")):
        return False
    if image and Path(parsed.path).suffix.lower() not in SUPPORTED_IMAGES:
        return False
    return True


def normalized_url(reference: str, page: str, *, image: bool = False) -> str | None:
    if not reference or reference.strip().lower().startswith(("data:", "blob:", "javascript:")):
        return None
    parsed = urlsplit(urljoin(page, reference.strip()))
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
    return url if public_url(url, image=image) else None


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_url(newurl, image=Path(urlsplit(req.full_url).path).suffix.lower() in SUPPORTED_IMAGES):
            raise ValueError("Redirect outside public MojPlayWin origin")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, method: str = "GET") -> tuple[int, str, bytes, str, str]:
    """Return status, content type, bytes, final URL, X-Robots-Tag."""
    if not public_url(url):
        raise ValueError("Nonpublic URL refused")
    req = Request(url, method=method, headers={"User-Agent": "MojPlayWinImageAudit/1.0 (+read-only)", "Accept": "text/html, application/xml, image/*"})
    with build_opener(SameOriginRedirect()).open(req, timeout=12) as response:
        data = response.read(4_000_001) if method == "GET" else b""
        if len(data) > 4_000_000:
            raise ValueError("Public document exceeds 4 MB audit limit")
        return (response.status, response.headers.get_content_type(), data,
                response.geturl(), response.headers.get("X-Robots-Tag", ""))


def sitemap_pages(xml: bytes, limit: int = 10000) -> list[str]:
    root = ET.fromstring(xml)
    if root.tag != "{" + NS_SITEMAP + "}urlset":
        raise ValueError("Expected canonical urlset, not sitemap index or HTML")
    urls = []
    for item in root.findall("{" + NS_SITEMAP + "}url"):
        loc = (item.findtext("{" + NS_SITEMAP + "}loc") or "").strip()
        if not public_url(loc):
            continue
        if loc not in urls:
            urls.append(loc)
        if len(urls) > limit:
            raise ValueError("Page count exceeds declared audit limit")
    return urls


def split_srcset(value: str) -> list[str]:
    """Handle ordinary HTML srcset candidates; do not treat data URLs as files."""
    return [candidate.strip().split()[0] for candidate in value.split(",") if candidate.strip()]


class PageImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        # The bool is True only for <img>, which actually supports alt text.
        self.images: list[tuple[str, str | None, bool]] = []
        self.html_img_tags = 0
        self.embedded_data_image_tags = 0
        self.deferred_image_tags = 0
        self.robots: list[str] = []
        self.canonical: str | None = None
        self._in_head = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        d = dict(attrs)
        if tag == "head":
            self._in_head = True
        if tag == "img":
            self.html_img_tags += 1
            if (d.get("src") or "").strip().lower().startswith("data:"):
                self.embedded_data_image_tags += 1
            if not d.get("src") and any(d.get(key) for key in ("data-src", "data-lazy-src", "data-original")):
                self.deferred_image_tags += 1
            if d.get("src"):
                self.images.append((d["src"], d.get("alt"), True))
            for candidate in split_srcset(d.get("srcset") or ""):
                self.images.append((candidate, d.get("alt"), True))
        if tag == "source":
            for candidate in split_srcset(d.get("srcset") or ""):
                self.images.append((candidate, None, False))
        if self._in_head and tag == "meta":
            if (d.get("name") or "").lower() in {"robots", "googlebot", "googlebot-image"}:
                self.robots.append(d.get("content") or "")
            if (d.get("property") or "").lower() == "og:image" and d.get("content"):
                self.images.append((d["content"], None, False))
        if self._in_head and tag == "link" and "canonical" in (d.get("rel") or "").lower().split():
            self.canonical = d.get("href")

    def handle_endtag(self, tag: str):
        if tag == "head":
            self._in_head = False


def blocked_by_robots(text: str) -> bool:
    tokens = {v.strip().lower() for v in re.split(r"[,;\s]+", text or "")}
    return "noindex" in tokens or "noimageindex" in tokens or "none" in tokens


def excluded_reference_reason(reference: str, page: str) -> str:
    """Give a useful reason without recording signed URLs or data-URI payloads."""
    lowered = reference.strip().lower()
    if lowered.startswith("data:"):
        return "embedded_data_uri"
    if lowered.startswith(("blob:", "javascript:")):
        return "non_http_image_reference"
    candidate = urlsplit(urljoin(page, reference.strip()))
    if candidate.netloc.lower() != "mojplaywin.com" or candidate.scheme != "https":
        return "outside_public_origin"
    if Path(candidate.path).suffix.lower() not in SUPPORTED_IMAGES:
        return "unsupported_public_image_extension"
    return "protected_or_signed_reference"


def audit(
    sitemap_xml: bytes,
    loader: Callable[[str, str], tuple[int, str, bytes, str, str]] = fetch,
    verify_images: bool = False,
) -> tuple[dict, dict[str, list[str]]]:
    pages = sitemap_pages(sitemap_xml)
    report = {"origin": ORIGIN, "sitemap_pages": len(pages), "pages_checked": 0,
              "indexable_pages": 0, "image_references": 0, "unique_public_images": 0,
              "html_img_tags": 0, "embedded_data_image_tags": 0,
              "deferred_image_tags": 0,
              "missing_alt_occurrences": 0, "empty_alt_occurrences": 0,
              "verified_image_urls": 0, "skipped_pages": [], "excluded_images": [],
              "unverified_images": [], "pages_without_images": [],
              "pages_without_html_img_tags": [], "pages_without_public_html_img_urls": [],
              "pages_with_embedded_data_images": [], "pages_with_deferred_images": [],
              "pages_with_metadata_only_images": []}
    image_pages: dict[str, list[str]] = {}
    all_images: set[str] = set()
    image_verified: dict[str, bool] = {}
    for page in pages:
        try:
            status, mime, html, final_url, header_robots = loader(page, "GET")
            report["pages_checked"] += 1
            if status != 200 or mime != "text/html" or final_url.rstrip("/") != page.rstrip("/"):
                report["skipped_pages"].append({"url": page, "reason": "response_not_canonical_html"})
                continue
            parsed = PageImages()
            parsed.feed(html.decode("utf-8", errors="replace"))
            canonical = normalized_url(parsed.canonical, page) if parsed.canonical else page
            if canonical.rstrip("/") != page.rstrip("/") or blocked_by_robots(" ".join(parsed.robots + [header_robots])):
                report["skipped_pages"].append({"url": page, "reason": "noncanonical_or_noindex"})
                continue
            report["indexable_pages"] += 1
            report["html_img_tags"] += parsed.html_img_tags
            report["embedded_data_image_tags"] += parsed.embedded_data_image_tags
            report["deferred_image_tags"] += parsed.deferred_image_tags
            if parsed.html_img_tags == 0:
                report["pages_without_html_img_tags"].append(page)
            if parsed.embedded_data_image_tags:
                report["pages_with_embedded_data_images"].append(page)
            if parsed.deferred_image_tags:
                report["pages_with_deferred_images"].append(page)
            discovered = []
            public_html_image_urls = set()
            for raw, alt, is_img in parsed.images:
                report["image_references"] += 1
                if is_img and alt is None:
                    report["missing_alt_occurrences"] += 1
                elif is_img and not alt.strip():
                    report["empty_alt_occurrences"] += 1
                src = normalized_url(raw, page, image=True)
                if not src:
                    report["excluded_images"].append({
                        "page": page, "reason": excluded_reference_reason(raw, page)})
                    continue
                if is_img:
                    public_html_image_urls.add(src)
                all_images.add(src)
                if verify_images and src not in image_verified:
                    try:
                        code, content_type, _, final, xr = loader(src, "HEAD")
                        image_verified[src] = bool(code == 200 and content_type.startswith("image/")
                                                   and final == src and not blocked_by_robots(xr))
                        if not image_verified[src]:
                            report["unverified_images"].append({"url": src, "reason": "status_mime_redirect_or_noimageindex"})
                    except (HTTPError, URLError, ValueError, OSError) as error:
                        image_verified[src] = False
                        report["unverified_images"].append({"url": src, "reason": type(error).__name__})
                if verify_images and not image_verified[src]:
                    continue
                if src not in discovered:
                    discovered.append(src)
            if not public_html_image_urls:
                report["pages_without_public_html_img_urls"].append(page)
                if discovered:
                    report["pages_with_metadata_only_images"].append(page)
            if not discovered:
                report["pages_without_images"].append(page)
            else:
                image_pages[page] = discovered
        except (HTTPError, URLError, ValueError, ET.ParseError, OSError) as error:
            report["skipped_pages"].append({"url": page, "reason": type(error).__name__})
    report["unique_public_images"] = len(all_images)
    report["verified_image_urls"] = sum(image_verified.values()) if verify_images else 0
    report["image_sitemap_page_entries"] = len(image_pages)
    report["image_sitemap_image_entries"] = sum(map(len, image_pages.values()))
    report["image_validation_mode"] = "verified_HEAD" if verify_images else "not_verified"
    return report, image_pages


def audit_parallel(
    sitemap_xml: bytes,
    loader: Callable[[str, str], tuple[int, str, bytes, str, str]] = fetch,
    *,
    workers: int = 3,
    verify_images: bool = False,
) -> tuple[dict, dict[str, list[str]], dict[str, list[str]]]:
    """Bounded, deterministic public GET/HEAD verification; never writes to site.

    Fetch responses concurrently only, then parse and report in sitemap order.
    The third return value is the unverified candidate inventory for evidence.
    """
    if workers not in (1, 2, 3, 4):
        raise ValueError("workers must be between 1 and 4")

    def attempt(url: str, method: str):
        try:
            return loader(url, method)
        except (HTTPError, URLError, ValueError, OSError) as error:
            return error

    pages = sitemap_pages(sitemap_xml)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        page_responses = dict(zip(pages, pool.map(lambda page: attempt(page, "GET"), pages)))

    def cached_loader(url: str, method: str):
        if method != "GET" or url not in page_responses:
            raise ValueError("Only the previously requested public page can be read")
        response = page_responses[url]
        if isinstance(response, Exception):
            raise response
        return response

    report, candidates = audit(sitemap_xml, loader=cached_loader, verify_images=False)
    report["public_page_fetch_workers"] = workers
    if not verify_images:
        return report, candidates, candidates

    unique_images = list(dict.fromkeys(image for images in candidates.values() for image in images))
    if len(unique_images) != report["unique_public_images"]:
        raise ValueError("Image inventory consistency check failed")

    def check_image(url: str) -> tuple[bool, str]:
        response = attempt(url, "HEAD")
        if isinstance(response, HTTPError) and response.code in (405, 501):
            # A missing HEAD handler is not a broken image. GET is the actual
            # retrieval method used by image crawlers; fetch retains a 4 MB cap.
            response = attempt(url, "GET")
        if isinstance(response, HTTPError):
            return False, "HTTP_" + str(response.code)
        if isinstance(response, Exception):
            return False, type(response).__name__
        status, mime, _, final, xrobots = response
        if status != 200 or not mime.startswith("image/") or final != url or blocked_by_robots(xrobots):
            return False, "status_mime_redirect_or_noimageindex"
        return True, "verified"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        checks = dict(zip(unique_images, pool.map(check_image, unique_images)))

    verified = {
        page: valid_urls
        for page, urls in candidates.items()
        if (valid_urls := [url for url in urls if checks[url][0]])
    }
    report["verified_image_urls"] = sum(ok for ok, _ in checks.values())
    report["unverified_images"] = [
        {"url": url, "reason": reason}
        for url, (ok, reason) in checks.items() if not ok
    ]
    report["image_sitemap_page_entries"] = len(verified)
    report["image_sitemap_image_entries"] = sum(map(len, verified.values()))
    report["image_validation_mode"] = "verified_HEAD_with_GET_on_405_501"
    report["pages_without_verified_images"] = [
        page for page in pages if page not in verified and page not in
        {item["url"] for item in report["skipped_pages"]}
    ]
    return report, verified, candidates


def xml_image_sitemap(image_pages: dict[str, list[str]]) -> bytes:
    ET.register_namespace("", NS_SITEMAP)
    ET.register_namespace("image", NS_IMAGE)
    root = ET.Element("{" + NS_SITEMAP + "}urlset")
    for page, urls in image_pages.items():
        row = ET.SubElement(root, "{" + NS_SITEMAP + "}url")
        ET.SubElement(row, "{" + NS_SITEMAP + "}loc").text = page
        for url in urls:
            image_tag = ET.SubElement(row, "{" + NS_IMAGE + "}image")
            ET.SubElement(image_tag, "{" + NS_IMAGE + "}loc").text = url
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def new_file_only(path: str, content: bytes):
    destination = Path(path)
    with destination.open("xb") as out:
        out.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", help="Write JSON report to a NEW local file")
    parser.add_argument("--image-sitemap", help="Write additive image sitemap to a NEW local file")
    parser.add_argument("--image-inventory", help="Write public image-to-page candidates to a NEW local JSON file")
    parser.add_argument("--verify-images", action="store_true", help="Validate HTTP 200 image/* for every image")
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=1,
                        help="Bounded concurrent public reads (1-4; default 1)")
    args = parser.parse_args()
    if args.image_sitemap and not args.verify_images:
        parser.error("--image-sitemap requires --verify-images; never publish unverified URLs")
    status, mime, xml, final, _ = fetch(SITEMAP)
    if status != 200 or mime not in {"application/xml", "text/xml"} or final != SITEMAP:
        parser.error("Live sitemap is missing or was redirected; refusing to generate a replacement")
    if args.workers > 1:
        report, entries, inventory = audit_parallel(xml, workers=args.workers,
                                                    verify_images=args.verify_images)
    else:
        report, entries = audit(xml, verify_images=args.verify_images)
        inventory = entries if not args.verify_images else {}
    if args.image_inventory:
        if args.verify_images and args.workers == 1:
            parser.error("Complete pre-verification inventory requires --workers 2, 3 or 4")
        new_file_only(args.image_inventory, (json.dumps(inventory, ensure_ascii=False, indent=2)
                                             + "\n").encode("utf-8"))
    if args.image_sitemap:
        if not entries:
            parser.error("Zero verified image entries; refusing to publish an empty image sitemap")
        new_file_only(args.image_sitemap, xml_image_sitemap(entries))
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.report:
        new_file_only(args.report, encoded)
    else:
        print(encoded.decode("utf-8"))


if __name__ == "__main__":
    main()
