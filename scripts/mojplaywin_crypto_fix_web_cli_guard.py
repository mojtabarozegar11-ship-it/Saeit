#!/usr/bin/env python3
"""Atomically fix only installed MojPlayWin standalone admin PHP CLI guard.

Must be stopped, zero invoices, and match exact reviewed old/new SHA256.
No Django, Apache, Passenger, shared DB or child changes.
"""
import hashlib
import os
from pathlib import Path
import secrets
import sqlite3
import sys

LIVE=Path("/home/zomorod2/mojplaywin.com/checkout/crypto/bootstrap.php")
FOLDER=LIVE.parent
PRIVATE=Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
BACKUP=PRIVATE/"pre-cli-http-guard-bootstrap.php.backup"

def digest(content):
    return hashlib.sha256(content).hexdigest()

def run(source,old_hash,new_hash):
    for folder in (FOLDER,PRIVATE):
        if not folder.is_dir() or folder.is_symlink():
            raise RuntimeError("Unsafe isolated gateway path")
    if LIVE.is_symlink() or not LIVE.is_file() or source.is_symlink() or not source.is_file():
        raise RuntimeError("Untrusted standalone PHP source")
    if (PRIVATE/"enabled.flag").exists() or (PRIVATE/"enabled.flag").is_symlink():
        raise RuntimeError("Cannot modify live payment handler when enabled")
    with sqlite3.connect("file:"+str(PRIVATE/"payments.sqlite3")+"?mode=ro",uri=True,timeout=5) as db:
        if db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]:
            raise RuntimeError("Payments exist; maintenance release refused")
    old=LIVE.read_bytes()
    new=source.read_bytes()
    if len(new)>50000 or len(new)<1000 or digest(new)!=new_hash:
        raise RuntimeError("New PHP bootstrap failed checksum validation")
    if digest(old)==new_hash:
        print("STANDALONE_PAYMENT_CLI_ALREADY_SECURED=true")
        return
    if digest(old)!=old_hash:
        raise RuntimeError("Live bootstrap version does not match review baseline")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise RuntimeError("Existing private rollback backup not overwritten")
    fd=os.open(str(BACKUP),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as handle:
        handle.write(old)
        handle.flush()
        os.fsync(handle.fileno())
    temporary=FOLDER/(".pending-bootstrap-"+secrets.token_hex(12))
    fd=os.open(str(temporary),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(new)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary,LIVE)
        if digest(LIVE.read_bytes())!=new_hash:
            raise RuntimeError("New bootstrap read-back checksum mismatch")
        print("STANDALONE_PAYMENT_CLI_HTTP_GUARD_INSTALLED=true")
        print("MERCHANT_PAYMENTS_ENABLED=false")
    except BaseException:
        if temporary.is_file():
            temporary.unlink()
        if LIVE.is_file() and digest(LIVE.read_bytes())==new_hash:
            restore=FOLDER/(".pending-bootstrap-rollback-"+secrets.token_hex(12))
            fd=os.open(str(restore),os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
            with os.fdopen(fd,"wb") as h:
                h.write(old)
                h.flush()
                os.fsync(h.fileno())
            restore.chmod(0o644)
            os.replace(restore,LIVE)
        raise

if __name__=="__main__":
    if len(sys.argv)!=4:
        raise SystemExit("usage: patch-cli.py new-bootstrap.php oldsha256 newsha256")
    run(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
