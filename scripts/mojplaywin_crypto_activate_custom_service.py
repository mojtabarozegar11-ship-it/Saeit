#!/usr/bin/env python3
"""Fail-closed activation of ONLY the independently hosted MojPlayWin
custom-service ETH/TRX receiving endpoint. No shared Django/Passenger writes.
No cron modifications, database row changes, or wallet signing.
"""
import hashlib
import os
import pathlib
import sqlite3
import subprocess
import shutil
import sys

SITE=pathlib.Path("/home/zomorod2/mojplaywin.com")
PHP=SITE/"checkout"/"crypto"/"index.php"
DATA=pathlib.Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
FLAG=DATA/"enabled.flag"
MARKER=b"MOJPLAYWIN_NATIVE_WATCH_ONLY_GATEWAY_V1\n"
CRON_MARK="/mojplaywin.com/checkout/crypto/index.php reconcile"
EXPECTED_WALLETS=[
    "0x89149b01f59115B86553561F12438D2ADF517E75",
    "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
    "414FD76FC6FB6370DCC86170E9695610EBF559DDAD",
]

def identity(expected):
    if not expected or len(expected)!=64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError("Untrusted expected source digest")
    for p in (SITE,PHP.parent,DATA):
        if p.is_symlink() or not p.is_dir():
            raise RuntimeError("Gateway isolation directory missing/symlinked")
    if PHP.is_symlink() or not PHP.is_file() or PHP.stat().st_size>300000:
        raise RuntimeError("Gateway PHP is missing/invalid")
    body=PHP.read_bytes()
    if hashlib.sha256(body).hexdigest()!=expected:
        raise RuntimeError("Reviewed source SHA differs from current deployment")
    for wallet in EXPECTED_WALLETS:
        if wallet.encode() not in body:
            raise RuntimeError("Merchant wallet or TRON hex mismatch")
    if shutil.which("php") is None or shutil.which("crontab") is None:
        raise RuntimeError("PHP CLI or cron not available")
    syntax=subprocess.run(["php","-l",str(PHP)],capture_output=True,timeout=12)
    if syntax.returncode:
        raise RuntimeError("Installed gateway has a PHP syntax error")
    cron=subprocess.run(["crontab","-l"],capture_output=True,timeout=12)
    if cron.returncode!=0 or len(cron.stdout)>400000:
        raise RuntimeError("Installed cron schedule could not be verified")
    entries=[l.strip() for l in cron.stdout.decode("utf-8","replace").splitlines()
             if l.strip() and not l.lstrip().startswith("#") and CRON_MARK in l]
    if len(entries)!=1:
        raise RuntimeError("Exactly one dedicated gateway reconciliation schedule required")
    minute=entries[0].split()[0]
    if minute not in ("*","*/1","*/2","*/3","*/4","*/5"):
        raise RuntimeError("Reconciliation cron is too infrequent or unrecognized")
    dbpath=DATA/"payments.sqlite3"
    key=DATA/"rate.key"
    if dbpath.is_symlink() or key.is_symlink() or not dbpath.is_file() or not key.is_file():
        raise RuntimeError("Missing private database/abuse limiter key")
    if len(key.read_bytes())!=32:
        raise RuntimeError("Invalid private rate key")
    db=sqlite3.connect(f"file:{dbpath}?mode=ro",uri=True,timeout=4)
    try:
        total=db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        paid=db.execute("SELECT COUNT(*) FROM invoices WHERE status='paid'").fetchone()[0]
        confirming=db.execute("SELECT COUNT(*) FROM invoices WHERE status='confirming'").fetchone()[0]
        schema={r[1] for r in db.execute("PRAGMA index_list('invoices')")}
        if "unique_merchant_quote" not in schema:
            raise RuntimeError("Permanent quote uniqueness constraint missing")
        if paid or confirming:
            raise RuntimeError("Existing in-flight settlements require operator reconciliation")
    finally:
        db.close()
    print("PAYMENT_CRON_VALIDATED_MINUTE="+minute)
    print("PREEXISTING_PAYMENT_INVOICE_COUNT="+str(total))
    print("PRODUCTION_GATEWAY_MATCHES_REVIEWED_SHA=true")
    print("PUBLIC_WALLET_RECEIVE_DESTINATIONS_MATCH=true")
    print("CHILD_SITE_OR_SHARED_DB_CHANGED=false")

def activate(expected):
    identity(expected)
    if FLAG.exists() or FLAG.is_symlink():
        raise RuntimeError("Payment enable flag exists already; refusing duplicate activation")
    oldmask=os.umask(0o077)
    try:
        fd=os.open(str(FLAG),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(MARKER)
            f.flush()
            os.fsync(f.fileno())
    finally:
        os.umask(oldmask)
    print("MOJPLAYWIN_CUSTOM_SERVICE_RECEIPT_GATEWAY_ENABLED=true")
    print("ALL_PRODUCTS_STORE_INTEGRATION_DONE=false")

def disable(expected):
    if DATA.is_symlink() or not DATA.is_dir() or FLAG.is_symlink():
        raise RuntimeError("Unsafe private flag")
    if FLAG.is_file():
        if FLAG.read_bytes()!=MARKER:
            raise RuntimeError("Unknown enable flag contents, refusing removal")
        FLAG.unlink()
    print("MOJPLAYWIN_CUSTOM_SERVICE_RECEIPT_GATEWAY_ENABLED=false")

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("activate","disable"):
        raise SystemExit("Usage: activation.py activate|disable EXPECTED_SHA256")
    cmd,digest=sys.argv[1:]
    if cmd=="activate":activate(digest)
    else:disable(digest)
