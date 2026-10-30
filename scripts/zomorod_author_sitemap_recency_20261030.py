#!/usr/bin/env python3
"""Safely correct the lastmod of one updated Persian author URL.

No sitemap links are added/removed; no unrelated URL elements are modified.
The existing cPanel sitemap is backed up before the one-entry atomic change.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
from xml.etree import ElementTree

TARGET = Path("/home/zomorod2/public_html/sitemap.xml")
BACKUP_ROOT = Path("/home/zomorod2/.backups/zm-author-sitemap-recency")
URL = "https://zomorodmelal.ir/authors/mojtaba-rozegar/"
OLD = (
    b"<url><loc>https://zomorodmelal.ir/authors/mojtaba-rozegar/</loc>"
    b"<lastmod>2026-10-23</lastmod></url>"
)
NEW = (
    b"<url><loc>https://zomorodmelal.ir/authors/mojtaba-rozegar/</loc>"
    b"<lastmod>2026-10-30</lastmod></url>"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transform(source: bytes) -> bytes:
    root = ElementTree.fromstring(source)
    if not root.tag.endswith("urlset"):
        raise ValueError("Sitemap is not a URL set")
    urls = [
        (element.text or "").strip()
        for element in root.iter()
        if element.tag.endswith("loc")
    ]
    if urls.count(URL) != 1:
        raise ValueError("Persian author URL not uniquely present")
    if source.count(OLD) != 1 or source.count(NEW):
        raise ValueError("Old author lastmod not exact or already updated")
    updated = source.replace(OLD, NEW, 1)
    ElementTree.fromstring(updated)
    if updated.replace(NEW, OLD, 1) != source:
        raise ValueError("Unrelated sitemap bytes changed")
    return updated


def safe_target() -> Path:
    if TARGET.is_symlink() or not TARGET.is_file() or TARGET.resolve() != TARGET:
        raise ValueError("Unexpected sitemap path")
    if TARGET.stat().st_size > 20_000_000:
        raise ValueError("Unexpected sitemap size")
    return TARGET


def backup_path(run_id: str) -> Path:
    if not re.fullmatch(r"[0-9]{6,24}", run_id):
        raise ValueError("Unsafe workflow run")
    return BACKUP_ROOT / run_id


def atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".zm-author-sitemap-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), stat.S_IMODE(path.stat().st_mode))
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def install(run_id: str) -> None:
    path = safe_target()
    before = path.read_bytes()
    if before.count(NEW) == 1 and before.count(OLD) == 0:
        print("AUTHOR_SITEMAP_ALREADY_CURRENT=YES", flush=True)
        return
    after = transform(before)
    folder = backup_path(run_id)
    if folder.exists() or folder.is_symlink():
        raise ValueError("Sitemap backup collision")
    folder.mkdir(parents=True, mode=0o700)
    saved = folder / "sitemap.before"
    with saved.open("xb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(before)
        out.flush()
        os.fsync(out.fileno())
    (folder / "sha.txt").write_text(
        digest(before) + "\n" + digest(after) + "\n", encoding="ascii"
    )
    (folder / "sha.txt").chmod(0o600)
    if saved.read_bytes() != before or digest(path.read_bytes()) != digest(before):
        raise ValueError("Sitemap backup or concurrent edit failed")
    atomic_write(path, after)
    if digest(path.read_bytes()) != digest(after):
        raise ValueError("Sitemap post-write hash mismatch")
    print("AUTHOR_SITEMAP_LASTMOD_INSTALLED=2026-10-30", flush=True)


def rollback(run_id: str) -> None:
    path = safe_target()
    folder = backup_path(run_id)
    if folder.is_symlink() or not (folder / "sha.txt").is_file():
        raise ValueError("No sitemap rollback backup")
    old = (folder / "sitemap.before").read_bytes()
    sha = (folder / "sha.txt").read_text(encoding="ascii").splitlines()
    if len(sha) != 2 or digest(old) != sha[0]:
        raise ValueError("Sitemap backup invalid")
    current = path.read_bytes()
    if digest(current) not in sha:
        raise ValueError("Concurrent sitemap change, rollback refused")
    if digest(current) == sha[1]:
        atomic_write(path, old)
    if digest(path.read_bytes()) != sha[0]:
        raise ValueError("Sitemap rollback hash mismatch")
    print("AUTHOR_SITEMAP_ROLLBACK=VERIFIED", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "install", "rollback"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.action == "rollback":
        if not args.run_id:
            parser.error("--run-id is required")
        rollback(args.run_id)
    elif args.action == "install":
        if not args.run_id:
            parser.error("--run-id is required")
        install(args.run_id)
    else:
        before = safe_target().read_bytes()
        if before.count(NEW) == 1 and before.count(OLD) == 0:
            print("AUTHOR_SITEMAP_ALREADY_CURRENT=YES", flush=True)
        else:
            transform(before)
            print("AUTHOR_SITEMAP_PREFLIGHT=PASS", flush=True)


if __name__ == "__main__":
    main()
