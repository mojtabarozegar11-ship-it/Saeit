#!/usr/bin/env python3
"""Read-only live MojPlayWin native payment safety and installation inventory.

No payment records, customer data, wallet identifiers, secrets or raw cron lines
leave the server. Never changes a file, process, DB, cron, or site.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import stat

SITE=Path("/home/zomorod2/mojplaywin.com")
APP=SITE/"checkout"/"crypto"
PRIVATE=Path("/home/zomorod2/.mojplaywin-crypto-payments-v1")
PAYMENTS=PRIVATE/"payments.sqlite3"
SAFE_FILES=("index.php","bootstrap.php")

def info(path):
    if path.is_symlink(): return {"exists":True,"symlink":True}
    if not path.exists(): return {"exists":False}
    s=path.stat()
    return {"exists":True,"symlink":False,"file":path.is_file(),
            "directory":path.is_dir(),"mode":oct(stat.S_IMODE(s.st_mode)),
            "size_bytes":s.st_size if path.is_file() else None}

def details():
    result={
        "classification":"MOJPLAYWIN_ISOLATED_GATEWAY_READONLY_LIVE_AUDIT",
        "site_is_real_dir":SITE.is_dir() and not SITE.is_symlink(),
        "payment_only_directory":info(APP),
        "private_payment_storage":info(PRIVATE),
        "customer_funds_sent_by_probe":False,
        "database_modified":False,
        "shared_django_touched":False,
        "protected_child_sites_touched":False,
        "real_purchase_or_wallet_receipt_verified":False,
        "fully_operational_store_proven":False,
    }
    result["files"]={}
    for name in SAFE_FILES:
        p=APP/name
        data=info(p)
        if data.get("file") and not data.get("symlink") and data.get("size_bytes",0)<300_000:
            data["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
        result["files"][name]=data
    flag=PRIVATE/"enabled.flag"
    result["payment_enabled_flag_present"]=flag.is_file() and not flag.is_symlink()
    result["payment_flag_symlink"]=flag.is_symlink()
    result["private_rate_key_present"]=(PRIVATE/"rate.key").is_file() and not (PRIVATE/"rate.key").is_symlink()
    result["private_database"]=info(PAYMENTS)
    if PAYMENTS.is_file() and not PAYMENTS.is_symlink():
        try:
            db=sqlite3.connect("file:"+str(PAYMENTS)+"?mode=ro",uri=True,timeout=3)
            try:
                result["sqlite_integrity_check"]=db.execute("PRAGMA quick_check").fetchone()[0]=="ok"
                names={v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                result["tables_present"]={n:n in names for n in ("invoices","throttle")}
                if "invoices" in names:
                    groups=db.execute("SELECT status,COUNT(*) FROM invoices GROUP BY status").fetchall()
                    result["invoice_counts_by_status"]={str(a):b for a,b in groups}
                    result["total_invoice_count"]=sum(b for _,b in groups)
                    result["paid_invoice_count"]=result["invoice_counts_by_status"].get("paid",0)
                    result["invoices_bound_to_tx_count"]=db.execute("SELECT COUNT(*) FROM invoices WHERE tx_hash IS NOT NULL").fetchone()[0]
                idx={v[1] for v in db.execute("PRAGMA index_list(invoices)")} if "invoices" in names else set()
                result["quote_unique_index_present"]="unique_merchant_quote" in idx
            finally: db.close()
        except (sqlite3.DatabaseError,OSError) as exc:
            result["db_read_failed_type"]=type(exc).__name__
    try:
        p=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=7)
        # Only boolean flags; never emit raw cron command lines, paths, secrets.
        lines=[line.strip() for line in p.stdout.splitlines() if line.strip() and not line.lstrip().startswith("#")] if p.returncode==0 else []
        result["cron_read_success"]=p.returncode==0
        result["payment_reconciler_cron_configured"]=any(
            "mojplaywin" in s.lower() and "reconcile" in s.lower() for s in lines
        )
        result["payment_reconcile_cron_count"]=sum("mojplaywin" in s.lower() and "reconcile" in s.lower() for s in lines)
    except (OSError,subprocess.TimeoutExpired):
        result["cron_read_success"]=False
    return result

if __name__=="__main__":
    print(json.dumps(details(),sort_keys=True,ensure_ascii=False))
