#!/usr/bin/env python3
"""Scoped, recoverable rewrite for the intermittent Android author-profile HTTP 500.

Only the exact /authors/mojtaba-rozegar/ route is changed; query strings are
preserved. The original .htaccess bytes are retained outside public_html.
Usage on the verified cPanel account: python3 - plan|apply|status|rollback
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
WEB = HOME / "public_html"
HT = WEB / ".htaccess"
INDEX = WEB / "authors/mojtaba-rozegar/index.html"
BACKUP_DIR = HOME / ".private-zm-author-route" / "utm-android-500-20261028"
BEFORE = BACKUP_DIR / "htaccess.before"
MANIFEST = BACKUP_DIR / "rewrite-manifest.json"
BEGIN = b"# BEGIN zm-author-utm-static-20261028"
END = b"# END zm-author-utm-static-20261028"
RULE = b"RewriteRule ^authors/mojtaba-rozegar/?$ /authors/mojtaba-rozegar/index.html [L,NC]"
PASSENGER_ANCHOR = b'PassengerAppRoot "/home/zomorod2/Saeit"'
ANCHOR = b"RewriteEngine On"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_paths() -> None:
    if Path.home() != HOME:
        raise RuntimeError("CPANEL_IDENTITY_MISMATCH")
    for path in (HOME, WEB, HT, INDEX.parent, INDEX, BACKUP_DIR.parent):
        if path.is_symlink():
            raise RuntimeError("SYMLINK_BLOCKED")
    if not HT.is_file() or not INDEX.is_file():
        raise RuntimeError("SITE_FILES_MISSING")
    if b'id="profile-name"' not in INDEX.read_bytes():
        raise RuntimeError("AUTHOR_IDENTITY_MARKER_MISSING")


def patched(original: bytes) -> bytes:
    if BEGIN in original or RULE in original:
        raise RuntimeError("REWRITE_ALREADY_EXISTS")
    if b"/authors/mojtaba-rozegar" in original:
        raise RuntimeError("UNEXPECTED_AUTHOR_RULE_CONFLICT")
    if PASSENGER_ANCHOR not in original:
        raise RuntimeError("PASSENGER_MAPPING_CHANGED")
    lines = original.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.strip() == ANCHOR]
    if not matches:
        raise RuntimeError("REWRITE_ENGINE_ANCHOR_MISSING")
    position = matches[0]
    if any(line.lstrip().startswith(b"RewriteRule ") for line in lines[:position]):
        raise RuntimeError("REWRITE_RULE_BEFORE_ENGINE")
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    block = newline.join((BEGIN, RULE, END)) + newline
    return b"".join(lines[:position + 1]) + block + b"".join(lines[position + 1:])


def atomic(path: Path, data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".author-safe-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def main(mode: str) -> None:
    safe_paths()
    current = HT.read_bytes()
    if mode == "plan":
        after = patched(current)
        print("AUTHOR_SCOPE=one_exact_route")
        print("AUTHOR_PLAN=valid")
        print("AUTHOR_BACKUP_PRESENT=" + str(BEFORE.exists()))
        print("AUTHOR_SOURCE_SHA=" + sha(current))
        print("AUTHOR_PLANNED_SHA=" + sha(after))
        return

    if mode == "apply":
        if BACKUP_DIR.is_symlink() or BEFORE.exists() or MANIFEST.exists():
            raise RuntimeError("BACKUP_ALREADY_PRESENT")
        after = patched(current)
        if not BACKUP_DIR.parent.is_dir():
            raise RuntimeError("PRIVATE_BACKUP_PARENT_MISSING")
        BACKUP_DIR.mkdir(mode=0o700)
        atomic(BEFORE, current, 0o600)
        info = {"before_sha256": sha(current), "after_sha256": sha(after),
                "route": "/authors/mojtaba-rozegar/"}
        atomic(MANIFEST, (json.dumps(info, sort_keys=True) + "\n").encode(), 0o600)
        if HT.read_bytes() != current:
            raise RuntimeError("CONCURRENT_HTACCESS_EDIT")
        mode_bits = stat.S_IMODE(HT.stat().st_mode)
        atomic(HT, after, mode_bits)
        if HT.read_bytes() != after:
            raise RuntimeError("PATCH_VERIFY_FAILED")
        print("AUTHOR_PATCH=applied")
        print("AUTHOR_PATCH_ROLLBACK_READY=yes")
        return

    if mode not in ("status", "rollback"):
        raise ValueError("INVALID_MODE")
    if BACKUP_DIR.is_symlink() or not BEFORE.is_file() or not MANIFEST.is_file():
        raise RuntimeError("BACKUP_OR_MANIFEST_MISSING")
    info = json.loads(MANIFEST.read_text())
    prior = BEFORE.read_bytes()
    if sha(prior) != info.get("before_sha256"):
        raise RuntimeError("BACKUP_HASH_MISMATCH")
    if mode == "status":
        print("AUTHOR_PATCH_STATUS=" + ("applied" if sha(current) == info["after_sha256"]
              else "rolled_back" if sha(current) == info["before_sha256"] else "drifted"))
        return
    if sha(current) != info["after_sha256"]:
        raise RuntimeError("ROLLBACK_CONCURRENT_CHANGE")
    atomic(HT, prior, stat.S_IMODE(HT.stat().st_mode))
    if HT.read_bytes() != prior:
        raise RuntimeError("ROLLBACK_VERIFY_FAILED")
    print("AUTHOR_PATCH=rolled_back")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: plan|apply|status|rollback")
    main(sys.argv[1])
