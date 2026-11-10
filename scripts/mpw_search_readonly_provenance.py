#!/usr/bin/env python3
"""Read-only MojPlayWin runtime provenance and organic-search metadata audit.

Run inside the existing cPanel account, never through an untrusted relay. No
network requests, subprocesses, secrets, file changes, or Django imports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_APP = Path("/home/zomorod2/Saeit-staging")
DEFAULT_SITE = Path("/home/zomorod2/mojplaywin.com")
MAX_SOURCE_BYTES = 2_000_000
TARGETS = {
    "product_template": "core/templates/brands/mojplaywin/product.html",
    "brand_views": "core/brand_views.py",
    "seo_views": "core/seo_views.py",
    "urlconf": "config/urls.py",
}


def _unsafe_symlink(path: Path) -> bool:
    """Reject symlink targets or ancestors before opening files."""
    return any(part.is_symlink() for part in (path, *path.parents))


def inspect_file(path: Path) -> tuple[dict, str | None]:
    if _unsafe_symlink(path):
        return {"state": "unsafe_symlink"}, None
    try:
        details = path.stat()
        if not stat.S_ISREG(details.st_mode):
            return {"state": "missing_or_non_regular"}, None
        if details.st_size > MAX_SOURCE_BYTES:
            return {"state": "oversized", "bytes": details.st_size}, None
        raw = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return {"state": "missing"}, None
    except (PermissionError, OSError):
        return {"state": "unreadable"}, None
    return {
        "state": "present",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "modified_utc": datetime.fromtimestamp(details.st_mtime, timezone.utc).isoformat(),
    }, raw.decode("utf-8", errors="replace")


def audit(app: Path, site: Path) -> dict:
    files = {}
    contents = {}
    for name, relative in TARGETS.items():
        files[name], contents[name] = inspect_file(app / relative)
    files["passenger_wsgi"], contents["passenger_wsgi"] = inspect_file(site / "passenger_wsgi.py")

    template = contents["product_template"] or ""
    lower = template.lower()
    jsonld = bool(re.search(r"application\s*/\s*ld\+json", lower))
    canonical = bool(re.search(r"rel\s*=\s*['\"]canonical['\"]", lower))
    wsgi = contents["passenger_wsgi"] or ""
    urls = contents["urlconf"] or ""
    return {
        "audit_version": "mpw-organic-discovery-provenance-v1",
        "read_only": True,
        "files": files,
        "signals": {
            "passenger_mentions_staging": "Saeit-staging" in wsgi,
            "product_template_jsonld_tag": jsonld,
            "product_template_canonical_tag": canonical,
            "product_template_product_type_literal": bool(re.search(r'@type[^\n]{0,160}Product', template)),
            "urlconf_mentions_robots": "robots.txt" in urls,
            "urlconf_mentions_sitemap": "sitemap.xml" in urls,
        },
        "limits": [
            "Source evidence is not proof that HTTP requests use these files.",
            "A static template scan cannot certify rendered JSON-LD correctness.",
            "Runtime imports, web requests, payments and email are not performed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, default=DEFAULT_APP)
    parser.add_argument("--site-root", type=Path, default=DEFAULT_SITE)
    args = parser.parse_args()
    result = audit(args.app_root, args.site_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(item["state"] == "present" for item in result["files"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
