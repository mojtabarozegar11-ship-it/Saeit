#!/usr/bin/env python3
"""Replace ONLY a known pre-installed MojPlayWin standalone PHP checkout entry.

Requires a closed payments feature flag, no existing invoices, and exact old
and new sha256 checksums. Preserves a private full-byte rollback copy.
Never touches the shared Django, Passenger, MySQL or any child subsite.
"""
import hashlib
import os
import secrets
import sqlite3
import sys
from pathlib import Path

TARGET=Path("/home/zomorod2/mojplaywin.com/checkout/crypto/index.php")
DIR=TARGET.parent
PRIVATE=Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
DB=PRIVATE/"payments.sqlite3"
BACKUP=PRIVATE/"pre-route-fix-index.php.backup"


def sha(contents):
    return hashlib.sha256(contents).hexdigest()


def upgrade(stage_file, old_sha, new_sha):
    for d in (DIR, PRIVATE):
        if not d.is_dir() or d.is_symlink():
            raise RuntimeError("Unsafe isolated gateway directory.")
    if TARGET.is_symlink() or not TARGET.is_file() or stage_file.is_symlink() or not stage_file.is_file():
        raise RuntimeError("Unsafe PHP path.")
    if (PRIVATE/"enabled.flag").exists() or (PRIVATE/"enabled.flag").is_symlink():
        raise RuntimeError("Cannot change an enabled payment handler.")
    if not DB.is_file() or DB.is_symlink():
        raise RuntimeError("Private payment storage unavailable.")
    with sqlite3.connect("file:"+str(DB)+"?mode=ro", uri=True, timeout=5) as conn:
        count=conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        if count!=0:
            raise RuntimeError("Already-issued invoices exist; upgrade refused.")
    old=TARGET.read_bytes()
    new=stage_file.read_bytes()
    if len(new)>200000 or len(new)<1000 or sha(new)!=new_sha:
        raise RuntimeError("New code integrity verification failed.")
    if sha(old)==new_sha:
        print("GATEWAY_ALREADY_UPDATED=true")
        return
    if sha(old)!=old_sha:
        raise RuntimeError("Current live gateway source differs from expected baseline.")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise RuntimeError("Old source backup already exists; refuse overwrite.")
    fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as handle:
        handle.write(old)
        handle.flush()
        os.fsync(handle.fileno())
    temp=DIR/(".pending-crypto-php-"+secrets.token_hex(12))
    fd=os.open(str(temp),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(new)
            handle.flush()
            os.fsync(handle.fileno())
        temp.chmod(0o644)
        os.replace(temp,TARGET)
        if sha(TARGET.read_bytes())!=new_sha:
            raise RuntimeError("Post-publish checksum mismatch.")
        print("GATEWAY_PAYMENT_ROUTE_FIXED_TO_EXPLICIT_INDEX_PHP=true")
        print("PAYMENTS_ENABLED=false")
        print("SHARED_DJANGO_CHANGED=false")
    except BaseException:
        if temp.exists():
            temp.unlink()
        if TARGET.is_file() and sha(TARGET.read_bytes())==new_sha:
            restore=DIR/(".pending-rollback-"+secrets.token_hex(12))
            fd=os.open(str(restore),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,"wb") as handle:
                handle.write(old)
                handle.flush()
                os.fsync(handle.fileno())
            restore.chmod(0o644)
            os.replace(restore,TARGET)
        raise


if __name__=="__main__":
    if len(sys.argv)!=4:
        raise SystemExit("usage: upgrade.py staged-new-index.php sha256-old sha256-new")
    upgrade(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
