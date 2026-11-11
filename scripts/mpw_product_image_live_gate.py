#!/usr/bin/env python3
"""Production image-discoverability release gate for MojPlayWin commerce.

READ ONLY: fetches five public HTML landing pages and two known public cover
assets. It does not mutate templates, publish sitemaps or request indexing.
The actual /store/ static fallback is checked, not a GitHub-only Django template.

Optional: --atelier-cover https://mojplaywin.com/path/to/verified-asset.webp
Only supply this after the third cover's real public URL has been established.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from mpw_google_images_audit import (
    ORIGIN, PageImages, blocked_by_robots, fetch, normalized_url, public_url,
)


COVERS = {
    72: ORIGIN + "/static/site/mojplaywin-products/chess-improvement.webp?v=20261026",
    225: ORIGIN + "/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026",
}
LANDINGS = ("/store/", "/store/product/72/", "/store/product/225/",
            "/store/product/879/", "/taniya/")


def valid_public_image_bytes(url: str, mime: str, body: bytes) -> bool:
    """Check bounded image-file framing, not just a 200/image MIME header.

    This does not replace a browser decode/visual check. Unsupported or
    inconsistent formats fail closed rather than being counted as verified.
    """
    if not body:
        return False
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix == ".webp" and mime == "image/webp":
        if (len(body) < 20 or body[:4] != b"RIFF" or body[8:12] != b"WEBP"
                or int.from_bytes(body[4:8], "little") + 8 != len(body)):
            return False
        offset = 12
        has_image_chunk = False
        while offset < len(body):
            if offset + 8 > len(body):
                return False
            kind = body[offset:offset + 4]
            size = int.from_bytes(body[offset + 4:offset + 8], "little")
            if kind in (b"VP8 ", b"VP8L", b"VP8X") and size:
                has_image_chunk = True
            offset += 8 + size + (size % 2)
            if offset > len(body):
                return False
        return has_image_chunk and offset == len(body)
    if suffix in (".jpeg", ".jpg") and mime == "image/jpeg":
        return len(body) > 4 and body.startswith(b"\xff\xd8\xff") and body.endswith(b"\xff\xd9")
    if suffix == ".png" and mime == "image/png":
        return (len(body) >= 45 and body.startswith(b"\x89PNG\r\n\x1a\n")
                and body[12:16] == b"IHDR" and
                int.from_bytes(body[16:20], "big") > 0 and
                int.from_bytes(body[20:24], "big") > 0 and
                body[-12:-8] == b"\x00\x00\x00\x00" and
                body[-8:-4] == b"IEND")
    if suffix == ".gif" and mime == "image/gif":
        return (len(body) >= 14 and body.startswith((b"GIF87a", b"GIF89a"))
                and body[6:8] != b"\x00\x00" and body[8:10] != b"\x00\x00"
                and body.endswith(b";"))
    if suffix == ".svg" and mime == "image/svg+xml":
        try:
            return ET.fromstring(body).tag == "{http://www.w3.org/2000/svg}svg"
        except ET.ParseError:
            return False
    return False


def inspect(loader=fetch, atelier_cover: str | None = None) -> dict:
    if atelier_cover is not None and not public_url(atelier_cover, image=True):
        raise ValueError("Atelier cover must be an unsigned public same-origin HTTPS image")
    expected = dict(COVERS)
    if atelier_cover:
        expected[879] = atelier_cover

    covers = {}
    for product_id, url in expected.items():
        http_valid = False
        structure_valid = False
        try:
            # A HEAD 200 and image/* MIME alone do not prove a renderable file.
            # Always fetch bounded image bytes; retain 405/501 HEAD fallback.
            try:
                status, mime, _, final, robots = loader(url, "HEAD")
            except HTTPError as err:
                if err.code not in (405, 501):
                    raise
                status, mime, _, final, robots = (200, "", b"", url, "")
            if status == 200 and final == url and not blocked_by_robots(robots):
                get_status, get_mime, body, get_final, get_robots = loader(url, "GET")
                http_valid = bool(get_status == 200 and get_mime.startswith("image/")
                                  and get_final == url and not blocked_by_robots(get_robots))
                structure_valid = http_valid and valid_public_image_bytes(url, get_mime, body)
        except (HTTPError, URLError, ValueError, OSError):
            pass
        covers[product_id] = {"url": url, "verified_http_image": http_valid,
                              "verified_file_structure": structure_valid}

    pages = []
    for path in LANDINGS:
        url = ORIGIN + path
        result = {"url": url, "status": "unavailable", "html_img_count": 0,
                  "public_direct_img_count": 0, "descriptive_alt_count": 0,
                  "embedded_data_img_count": 0,
                  "invalid_embedded_data_img_count": 0,
                  "renderer_marker": "not_detected", "issues": []}
        try:
            status, mime, html, final, header_robots = loader(url, "GET")
            if status != 200 or mime != "text/html" or final != url:
                result["issues"].append("noncanonical_or_non_html_response")
                pages.append(result)
                continue
            parsed = PageImages()
            parsed.feed(html.decode("utf-8", errors="replace"))
            result["status"] = "fetched"
            if path == "/store/" and b"MPW_STATIC_STORE_FALLBACK_V1" in html:
                result["renderer_marker"] = "MPW_STATIC_STORE_FALLBACK_V1"
            result["html_img_count"] = parsed.html_img_tags
            result["embedded_data_img_count"] = parsed.embedded_data_image_tags
            result["invalid_embedded_data_img_count"] = parsed.invalid_embedded_data_image_tags
            direct = [
                (image, alt) for raw, alt in parsed.direct_img_sources
                if (image := normalized_url(raw, url, image=True))
            ]
            result["public_direct_img_count"] = len(direct)
            result["descriptive_alt_count"] = sum(bool((alt or "").strip())
                                                  for _, alt in direct)
            if not parsed.canonical:
                result["issues"].append("missing_canonical")
            elif normalized_url(parsed.canonical, url) != url:
                result["issues"].append("nonself_canonical")
            if blocked_by_robots(" ".join(parsed.robots + [header_robots])):
                result["issues"].append("noindex_or_noimageindex")
            if not direct:
                result["issues"].append("no_public_direct_img_src")
            if any(not (alt or "").strip() for _, alt in direct):
                result["issues"].append("direct_img_missing_descriptive_alt_review")
            if parsed.embedded_data_image_tags:
                result["issues"].append("embedded_image_data_uri")
            if parsed.invalid_embedded_data_image_tags:
                result["issues"].append("invalid_embedded_image_data_uri")

            if path == "/store/":
                for product_id, cover in expected.items():
                    if cover not in {u for u, _ in direct}:
                        result["issues"].append(f"cover_{product_id}_absent_from_html")
                    if not covers[product_id]["verified_file_structure"]:
                        result["issues"].append(f"cover_{product_id}_invalid_public_asset")
            elif path.startswith("/store/product/"):
                product_id = int(path.strip("/").split("/")[-1])
                cover = expected.get(product_id)
                if cover is None:
                    result["issues"].append("product_cover_url_unknown")
                elif cover not in {u for u, _ in direct}:
                    result["issues"].append(f"cover_{product_id}_absent_from_html")
                if cover is not None and not covers[product_id]["verified_file_structure"]:
                    result["issues"].append(f"cover_{product_id}_invalid_public_asset")
        except (HTTPError, URLError, ValueError, OSError) as exc:
            result["issues"].append("fetch_failed_" + type(exc).__name__)
        pages.append(result)

    failures = sum(bool(page["issues"]) for page in pages)
    validated = sum(cover["verified_file_structure"] for cover in covers.values())
    release_ready = (failures == 0 and len(expected) == 3 and validated == 3)
    return {"site": ORIGIN, "read_only": True, "release_gate":
            "PASS" if release_ready else "HOLD", "pages_checked": len(pages),
            "store_live_renderer_marker": pages[0]["renderer_marker"],
            "pages_with_issues": failures, "known_cover_urls": len(expected),
            "verified_cover_urls": validated, "covers": covers, "pages": pages,
            "scope": "five commercial/editorial landing pages, not all site images",
            "image_validation_mode": "HTTP_HEAD_plus_bounded_GET_file_structure",
            "note": "File framing is not full visual decoding; browser validation, Google indexing and deployment permission remain separate."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atelier-cover", help="Verified public image URL for product 879")
    args = parser.parse_args()
    report = inspect(atelier_cover=args.atelier_cover)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["release_gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

