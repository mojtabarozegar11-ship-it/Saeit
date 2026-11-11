#!/usr/bin/env python3
"""Compare two already-captured XML sitemaps before approving an SEO release.

This tool only reads local XML snapshots. It does not fetch URLs, contact a
server, edit files, or authorize deployment. A successful result proves only
that the *supplied snapshots* satisfy the structural and parity checks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_SITEMAP_BYTES = 5 * 1024 * 1024
MAX_LOC_COUNT = 50_000
MAX_LOC_LENGTH = 2048


class SitemapParityError(ValueError):
    """Snapshot fails the read-only sitemap validation."""


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port is not None or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise SitemapParityError("Origin must be a bare HTTPS hostname, e.g. https://example.com")
    return parsed.hostname.lower()


def read_urls(snapshot: Path, host: str) -> set[str]:
    """Return canonical same-origin loc values; fail closed on invalid XML."""
    if not snapshot.is_file() or snapshot.is_symlink():
        raise SitemapParityError(f"Missing, non-regular or symlink snapshot: {snapshot}")
    if snapshot.stat().st_size > MAX_SITEMAP_BYTES:
        raise SitemapParityError(f"Oversize snapshot: {snapshot}")
    try:
        root = ElementTree.fromstring(snapshot.read_bytes())
    except ElementTree.ParseError as exc:
        raise SitemapParityError(f"Invalid XML in {snapshot}: {exc}") from exc
    if root.tag != f"{{{SITEMAP_NS}}}urlset":
        raise SitemapParityError(f"Expected a sitemap urlset, not {root.tag!r}")

    urls: set[str] = set()
    for element in root.findall(f"{{{SITEMAP_NS}}}url"):
        if len(urls) >= MAX_LOC_COUNT:
            raise SitemapParityError("Sitemap exceeds safe URL count")
        loc = element.findtext(f"{{{SITEMAP_NS}}}loc")
        if not loc or loc != loc.strip() or len(loc) > MAX_LOC_LENGTH:
            raise SitemapParityError(f"Invalid or missing loc in {snapshot}")
        parsed = urlsplit(loc)
        if (parsed.scheme != "https" or parsed.hostname != host or parsed.username
                or parsed.password or parsed.port is not None or not parsed.path.startswith("/")
                or parsed.query or parsed.fragment):
            raise SitemapParityError(f"Cross-host or noncanonical loc in {snapshot}: {loc}")
        if loc in urls:
            raise SitemapParityError(f"Duplicate loc in {snapshot}: {loc}")
        urls.add(loc)
    if not urls:
        raise SitemapParityError(f"Empty sitemap: {snapshot}")
    return urls


def compare(before: Path, after: Path, origin: str, required_paths: list[str]) -> dict:
    host = _origin(origin)
    old_urls = read_urls(before, host)
    new_urls = read_urls(after, host)
    missing = sorted(old_urls - new_urls)
    added = sorted(new_urls - old_urls)
    required = set()
    for path in required_paths:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise SitemapParityError(f"Required path must be a plain absolute path: {path}")
        required.add(f"https://{host}{path}")
    missing_required = sorted(required - new_urls)
    result = {
        "origin": f"https://{host}",
        "before_urls": len(old_urls),
        "after_urls": len(new_urls),
        "added_count": len(added),
        "removed_count": len(missing),
        "missing_required_count": len(missing_required),
        "status": "PASS" if not missing and not missing_required else "HOLD",
        "removed_examples": missing[:10],
        "missing_required": missing_required[:10],
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Existing public sitemap snapshot")
    parser.add_argument("--after", type=Path, required=True, help="Proposed sitemap snapshot")
    parser.add_argument("--origin", required=True, help="Expected HTTPS site origin")
    parser.add_argument("--required-path", action="append", default=[], help="Protected path; repeat as needed")
    args = parser.parse_args(argv)
    try:
        result = compare(args.before, args.after, args.origin, args.required_path)
    except (OSError, SitemapParityError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
