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
from urllib.error import HTTPError, URLError

from mpw_google_images_audit import (
    ORIGIN, PageImages, blocked_by_robots, fetch, normalized_url, public_url,
)


COVERS = {
    72: ORIGIN + "/static/site/mojplaywin-products/chess-improvement.webp?v=20261026",
    225: ORIGIN + "/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026",
}
LANDINGS = ("/store/", "/store/product/72/", "/store/product/225/",
            "/store/product/879/", "/taniya/")


def inspect(loader=fetch, atelier_cover: str | None = None) -> dict:
    if atelier_cover is not None and not public_url(atelier_cover, image=True):
        raise ValueError("Atelier cover must be an unsigned public same-origin HTTPS image")
    expected = dict(COVERS)
    if atelier_cover:
        expected[879] = atelier_cover

    covers = {}
    for product_id, url in expected.items():
        try:
            # HEAD-only responses can be blocked while GET works. A bounded
            # GET is used only on 405/501, as in the site-wide image audit.
            try:
                status, mime, _, final, robots = loader(url, "HEAD")
            except HTTPError as err:
                if err.code not in (405, 501):
                    raise
                status, mime, _, final, robots = loader(url, "GET")
            valid = (status == 200 and mime.startswith("image/") and
                     final == url and not blocked_by_robots(robots))
        except (HTTPError, URLError, ValueError, OSError):
            valid = False
        covers[product_id] = {"url": url, "verified_http_image": valid}

    pages = []
    for path in LANDINGS:
        url = ORIGIN + path
        result = {"url": url, "status": "unavailable", "html_img_count": 0,
                  "public_direct_img_count": 0, "descriptive_alt_count": 0,
                  "embedded_data_img_count": 0,
                  "invalid_embedded_data_img_count": 0, "issues": []}
        try:
            status, mime, html, final, header_robots = loader(url, "GET")
            if status != 200 or mime != "text/html" or final != url:
                result["issues"].append("noncanonical_or_non_html_response")
                pages.append(result)
                continue
            parsed = PageImages()
            parsed.feed(html.decode("utf-8", errors="replace"))
            result["status"] = "fetched"
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
            elif path.startswith("/store/product/"):
                product_id = int(path.strip("/").split("/")[-1])
                cover = expected.get(product_id)
                if cover is None:
                    result["issues"].append("product_cover_url_unknown")
                elif cover not in {u for u, _ in direct}:
                    result["issues"].append(f"cover_{product_id}_absent_from_html")
        except (HTTPError, URLError, ValueError, OSError) as exc:
            result["issues"].append("fetch_failed_" + type(exc).__name__)
        pages.append(result)

    failures = sum(bool(page["issues"]) for page in pages)
    validated = sum(cover["verified_http_image"] for cover in covers.values())
    release_ready = (failures == 0 and len(expected) == 3 and validated == 3)
    return {"site": ORIGIN, "read_only": True, "release_gate":
            "PASS" if release_ready else "HOLD", "pages_checked": len(pages),
            "pages_with_issues": failures, "known_cover_urls": len(expected),
            "verified_cover_urls": validated, "covers": covers, "pages": pages,
            "scope": "five commercial/editorial landing pages, not all site images",
            "note": "This does not prove Google indexing or permission to deploy."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--atelier-cover", help="Verified public image URL for product 879")
    args = parser.parse_args()
    report = inspect(atelier_cover=args.atelier_cover)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["release_gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

