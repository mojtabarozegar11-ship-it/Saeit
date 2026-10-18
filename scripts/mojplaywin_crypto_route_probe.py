#!/usr/bin/env python3
"""TEMPORARY isolated PHP routing test for MojPlayWin main domain only.

Never edits an existing file or any Django/Passenger config; no database,
payments, private keys, network requests or Passenger restarts.
Stage only in a previously absent checkout/crypto directory. Remove only our
identifiable marker file, and clean up directories only if empty.
"""
import hashlib
import os
from pathlib import Path
import sys

ROOT = Path("/home/zomorod2/mojplaywin.com")
PARENT = ROOT / "checkout"
CHILD = PARENT / "crypto"
FILE = CHILD / "__moj_gateway_probe_20261018.php"
MARKER = "MOJPLAYWIN-PHP-ROUTE-ISOLATION-20261018-v1"
BODY = "<?php header('Content-Type: text/plain; charset=utf-8'); header('Cache-Control: no-store'); echo '"+MARKER+"';"
HASH = hashlib.sha256(BODY.encode()).hexdigest()

def safe(path):
    if path.is_symlink():
        raise RuntimeError("Symlink refused")
    if path.exists() and not path.is_dir():
        raise RuntimeError("Unexpected non-directory in isolated route")

def stage():
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError("Main docroot unavailable")
    for p in (PARENT,CHILD):
        safe(p)
    if PARENT.exists() or CHILD.exists() or FILE.exists() or FILE.is_symlink():
        raise RuntimeError("Route not fresh; refusing to modify existing path")
    PARENT.mkdir(mode=0o755)
    try:
        CHILD.mkdir(mode=0o755)
        fd=os.open(str(FILE),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o644)
        with os.fdopen(fd,"wb") as f:
            f.write(BODY.encode())
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        cleanup()
        raise
    print("GATEWAY_TEMP_PHP_PROBE_STAGED=true")

def cleanup():
    if FILE.is_symlink():
        raise RuntimeError("Unsafe marker symlink")
    if FILE.is_file():
        if hashlib.sha256(FILE.read_bytes()).hexdigest()!=HASH:
            raise RuntimeError("Probe changed since stage; refusing to remove")
        FILE.unlink()
    for folder in (CHILD,PARENT):
        if folder.is_dir() and not folder.is_symlink():
            try:
                folder.rmdir()  # only empty dirs are removable
            except OSError:
                pass
    print("GATEWAY_TEMP_PHP_PROBE_CLEANUP_ATTEMPTED=true")

if __name__=="__main__":
    if sys.argv[1:]==["stage"]:
        stage()
    elif sys.argv[1:]==["cleanup"]:
        cleanup()
    else:
        raise SystemExit(2)
