#!/usr/bin/env python3
"""Create/rollback only the crypto subdirectory's new .htaccess.

This refuses to operate on existing or symlinked files, disabled-only staging,
and performs zero operations in the shared app or other subsite directories.
"""
import hashlib
import os
import sys
from pathlib import Path

WEBROOT = Path("/home/zomorod2/mojplaywin.com")
GATEWAY = WEBROOT / "checkout" / "crypto"
PRIVATE_FLAG = Path("/home/zomorod2/.mojplaywin-crypto-payments-v1/enabled.flag")
TARGET = GATEWAY / ".htaccess"

def check():
    if PRIVATE_FLAG.exists() or PRIVATE_FLAG.is_symlink():
        raise RuntimeError("Payment flag exists; do not modify routing while enabled.")
    if WEBROOT.is_symlink() or not WEBROOT.is_dir():
        raise RuntimeError("Unsafe web root")
    if GATEWAY.is_symlink() or not GATEWAY.is_dir():
        raise RuntimeError("Missing isolated gateway")
    for name in ("index.php", "bootstrap.php"):
        p = GATEWAY / name
        if p.is_symlink() or not p.is_file():
            raise RuntimeError("Standalone gateway missing")

def stage(src, digest):
    check()
    if TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError("Existing .htaccess refused; no overwrite allowed")
    if src.is_symlink() or not src.is_file() or src.stat().st_size > 2048:
        raise RuntimeError("Invalid source")
    data = src.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError("Expected digest mismatch")
    handle = os.open(str(TARGET), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        cleanup(digest)
        raise
    print("PAYMENT_ONLY_HTACCESS_STAGED=true")

def cleanup(digest):
    check()
    if TARGET.is_symlink():
        raise RuntimeError("Refuse symlink removal")
    if TARGET.is_file():
        if hashlib.sha256(TARGET.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Unexpected modification; refusing removal")
        TARGET.unlink()
    print("PAYMENT_ONLY_HTACCESS_CLEANUP_CONFIRMED=true")

def verify(digest):
    check()
    if TARGET.is_symlink() or not TARGET.is_file():
        raise RuntimeError("Missing isolated routing file")
    if hashlib.sha256(TARGET.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Isolated routing differs from reviewed source")
    print("PAYMENT_ONLY_HTACCESS_VERIFIED=true")

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("stage", "cleanup", "verify"):
        raise SystemExit("Usage: script.py stage|cleanup|verify source digest")
    action, filename, expected = sys.argv[1:]
    if len(expected) != 64:
        raise SystemExit("Invalid digest")
    if action == "stage":
        stage(Path(filename), expected)
    elif action == "cleanup":
        cleanup(expected)
    else:
        verify(expected)
