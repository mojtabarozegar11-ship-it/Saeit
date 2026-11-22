#!/usr/bin/env python3
"""Exact-scope Cache-Control for one immutable Zomorod homepage JS asset.

Never alters the homepage, Django, databases, or parent .htaccess. The only
public write is a new .htaccess inside the dedicated runtime asset directory.
If public HTTP verification fails, that new file moves into private quarantine.
Default command is an entirely read-only preflight.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from urllib.request import Request, urlopen


HOME = Path("/home/zomorod2/public_html/index.html")
ASSET_DIR = Path("/home/zomorod2/public_html/static/site/zomorod-perf")
ASSET_NAME = "zomorod-home-runtime-e0455f2cafacaee34b5c.js"
ASSET = ASSET_DIR / ASSET_NAME
CONFIG = ASSET_DIR / ".htaccess"
PRIVATE_DIR = Path("/home/zomorod2/.private/zomorod-js-cache-config")
HOME_SHA = "99e9c38cd20aaf400a3c68c2064211dc48d4ff0e518ee4815061ea0ca2626edc"
JS_SHA = "e0455f2cafacaee34b5c6cfba8157af575caeda1df6c8f64e92b6575c944ca07"
CACHE_VALUE = "public, max-age=31536000, immutable"
CONFIG_BYTES = (
    "# Zomorod immutable homepage runtime only; do not change parent rules.\n"
    "<IfModule mod_headers.c>\n"
    f"  <Files \"{ASSET_NAME}\">\n"
    f"    Header always set Cache-Control \"{CACHE_VALUE}\"\n"
    "  </Files>\n"
    "</IfModule>\n"
).encode("ascii")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def preflight(expect_no_config: bool = False) -> dict:
    for path in (HOME.parent, ASSET_DIR.parent.parent, ASSET_DIR.parent,
                 ASSET_DIR, ASSET, CONFIG, PRIVATE_DIR.parent, PRIVATE_DIR):
        if path.is_symlink():
            raise RuntimeError(f"Symlink path refused: {path}")
    if not HOME.is_file() or sha(HOME.read_bytes()) != HOME_SHA:
        raise RuntimeError("Approved optimized homepage SHA mismatch")
    if not ASSET.is_file() or sha(ASSET.read_bytes()) != JS_SHA:
        raise RuntimeError("Immutable JavaScript SHA mismatch")
    if expect_no_config and CONFIG.exists():
        raise RuntimeError("Existing directory .htaccess must be reviewed separately")
    if os.statvfs(str(ASSET_DIR)).f_bavail * os.statvfs(str(ASSET_DIR)).f_frsize < 50_000_000:
        raise RuntimeError("Insufficient free disk for safe publication")
    return {"home_sha256": HOME_SHA, "asset_sha256": JS_SHA,
            "config_exists": CONFIG.exists(), "desired_cache_control": CACHE_VALUE}


def verify_public() -> None:
    url = ("https://zomorodmelal.ir/static/site/zomorod-perf/" + ASSET_NAME
           + "?zm_cache_verify=" + JS_SHA[:20])
    request = Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urlopen(request, timeout=22) as response:
        content = response.read(400_000)
        actual_cache = response.headers.get("Cache-Control", "")
        mime = response.headers.get("Content-Type", "").lower()
        if response.status != 200 or "javascript" not in mime:
            raise RuntimeError("Live JavaScript HTTP/MIME verification failed")
        if sha(content) != JS_SHA:
            raise RuntimeError("Public JavaScript content has changed")
        if CACHE_VALUE not in actual_cache:
            raise RuntimeError(f"Expected Cache-Control header absent: {actual_cache!r}")


def quarantine_exact() -> Path:
    if CONFIG.is_symlink() or not CONFIG.is_file() or CONFIG.read_bytes() != CONFIG_BYTES:
        raise RuntimeError("Refuse to move a third-party or modified cache file")
    if PRIVATE_DIR.is_symlink() or PRIVATE_DIR.parent.is_symlink():
        raise RuntimeError("Private quarantine symlink refused")
    PRIVATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived = PRIVATE_DIR / f"reverted-cache-{timestamp}-{sha(CONFIG_BYTES)[:10]}.htaccess"
    if archived.exists():
        raise FileExistsError("Private quarantine collision")
    os.replace(CONFIG, archived)
    if archived.read_bytes() != CONFIG_BYTES:
        raise RuntimeError("Quarantine verification failed")
    return archived


def apply() -> None:
    preflight(expect_no_config=True)
    with tempfile.NamedTemporaryFile(dir=ASSET_DIR, prefix=".zm-cache-", delete=False) as f:
        pending = Path(f.name)
        try:
            os.fchmod(f.fileno(), 0o644)
            f.write(CONFIG_BYTES)
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            pending.unlink(missing_ok=True)
            raise
    try:
        # Exclusive link: no overwrite even if another maintainer raced us.
        os.link(pending, CONFIG, follow_symlinks=False)
    finally:
        pending.unlink(missing_ok=True)
    try:
        verify_public()
        preflight()
    except Exception:
        quarantine_exact()
        raise
    print(json.dumps({"mode": "published_and_verified", "cache_control": CACHE_VALUE,
                      "home_sha256": HOME_SHA, "asset_sha256": JS_SHA}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    if args.apply:
        apply()
    elif args.rollback:
        preflight()
        archived = quarantine_exact()
        print(json.dumps({"mode": "rolled_back", "quarantine": str(archived)}))
    else:
        print(json.dumps({**preflight(), "mode": "read_only"}))


if __name__ == "__main__":
    main()
