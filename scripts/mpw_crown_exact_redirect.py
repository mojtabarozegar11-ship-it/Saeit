#!/usr/bin/env python3
"""Exactly one new Crown Defender spelling redirect in an attested .htaccess.

Guarded by live SHA and the existing canonical rule; no unrelated mutation.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

HOME = Path("/home/zomorod2")
ROOT = HOME / "mojplaywin.com"
TARGET = ROOT / ".htaccess"
BACKUPS = HOME / ".mpw-crown-exact-alias-backups"
BEFORE_SHA = "a1a2e42ab3e001f3eca6ee2027d409ee8c40d6b87cf91b9e66106bd841909b48"
ANCHOR_LINES = (
    b"RewriteCond %{REQUEST_METHOD} ^GET$",
    b"RewriteCond %{REQUEST_URI} ^/games/crown-defender/?$",
)
BLOCK_LINES = (
    b"# Crown Defender typo compatibility; exact path only (2026-10-22).",
    b"RewriteCond %{REQUEST_METHOD} ^GET$",
    b"RewriteCond %{REQUEST_URI} ^/games/corwn-defender/?$",
    b"RewriteRule ^.*$ /games/crown-defender/ [R=301,L]",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def stop(reason):
    raise RuntimeError("CROWN_EXACT_REWRITE_SAFE_ABORT: " + reason)


def names(run):
    if not re.fullmatch(r"[0-9]{8,16}", run):
        stop("Invalid run ID")
    return (BACKUPS / ("before-" + run + ".htaccess"),
            BACKUPS / ("receipt-" + run + ".json"))


def validate_target():
    if ROOT.is_symlink() or not ROOT.is_dir() or TARGET.is_symlink() or not TARGET.is_file():
        stop("No exact regular root htaccess")


def insert_alias(original):
    separator = b"\r\n" if b"\r\n" in original else b"\n"
    anchor = separator.join(ANCHOR_LINES)
    if original.count(anchor) != 1:
        stop("Canonical Crown rule changed or duplicated")
    if b"/games/corwn-defender/" in original:
        stop("Legacy alias already defined")
    block = separator.join(BLOCK_LINES) + separator
    newer = original.replace(anchor, block + anchor, 1)
    if newer.count(block) != 1:
        stop("Unexpected patch shape")
    if newer.replace(block, b"", 1) != original:
        stop("Patch alters unrelated bytes")
    return newer


def atomic_replace(data, mode):
    fd, temp = tempfile.mkstemp(prefix=".crown-exact-redirect-", dir=str(ROOT))
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, TARGET)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def install(run):
    validate_target()
    backup, receipt = names(run)
    if backup.exists() or receipt.exists():
        stop("Duplicate run receipt")
    before = TARGET.read_bytes()
    if digest(before) != BEFORE_SHA:
        stop("Live htaccess changed since read-only audit")
    after = insert_alias(before)
    mode = stat.S_IMODE(TARGET.stat().st_mode)
    if BACKUPS.is_symlink():
        stop("Unsafe backup parent")
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    with backup.open("xb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(before)
        f.flush()
        os.fsync(f.fileno())
    with receipt.open("x", encoding="utf-8") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump({"run": run, "before": BEFORE_SHA, "after": digest(after),
                   "target": str(TARGET), "mode": mode}, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    if digest(TARGET.read_bytes()) != BEFORE_SHA:
        stop("Concurrent modification before commit")
    atomic_replace(after, mode)
    if digest(TARGET.read_bytes()) != digest(after):
        stop("After-write verification failed")
    print("CROWN_EXACT_REDIRECT_INSTALLED=YES")
    print("CROWN_EXACT_REDIRECT_SHA256=" + digest(after))


def get_receipt(run):
    backup, receipt = names(run)
    if (not backup.is_file() or backup.is_symlink() or not receipt.is_file()
            or receipt.is_symlink()):
        stop("Missing private backup/receipt")
    item = json.loads(receipt.read_text("utf-8"))
    if item.get("before") != BEFORE_SHA or item.get("target") != str(TARGET):
        stop("Receipt does not belong to this exact target")
    if digest(backup.read_bytes()) != BEFORE_SHA:
        stop("Private backup does not match baseline")
    return backup, item


def status(run):
    validate_target()
    _, item = get_receipt(run)
    if digest(TARGET.read_bytes()) != item["after"]:
        stop("Installed htaccess digest mismatch")
    print("CROWN_EXACT_REDIRECT_VERIFIED=YES")


def rollback(run):
    validate_target()
    backup, item = get_receipt(run)
    current = digest(TARGET.read_bytes())
    if current == item["after"]:
        atomic_replace(backup.read_bytes(), item["mode"])
    elif current != item["before"]:
        stop("Concurrent edit: refuse to overwrite")
    if digest(TARGET.read_bytes()) != BEFORE_SHA:
        stop("Rollback digest mismatch")
    print("CROWN_EXACT_REDIRECT_ROLLBACK=VERIFIED")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) != 2 or args[0] not in ("install", "status", "rollback"):
        stop("Usage: install|status|rollback RUN_ID")
    {"install": install, "status": status, "rollback": rollback}[args[0]](args[1])
