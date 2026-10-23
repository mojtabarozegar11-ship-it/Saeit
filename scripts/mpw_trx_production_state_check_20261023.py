#!/usr/bin/env python3
"""Privacy-preserving production TRX gateway diagnostic; strictly no writes."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
APP=Path("/home/zomorod2/Saeit-staging")
DOMAIN=Path("/home/zomorod2/mojplaywin.com")
if APP.is_symlink() or not APP.is_dir() or DOMAIN.is_symlink():
    raise RuntimeError("Unexpected production application")
if "APP='/home/zomorod2/Saeit-staging'" not in (DOMAIN/"passenger_wsgi.py").read_text("utf8","replace"):
    raise RuntimeError("Unexpected Passenger source")
os.chdir(APP)
sys.path.insert(0,str(APP))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")

def inspect():
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.urls import resolve
    from core.models import PaymentIntent
    from services.mpw_walletless_commercial_intent import (
        PROVIDER,WAITING,_commercial_db,_paid_read_db,
    )
    from services.mpw_trx_reconcile_cursor import read_cursor,pick_pending_page
    from services.mpw_trx_walletless_core import PaymentHold

    result={"scope":"production-read-only-mojplaywin-trx",
            "financial_writes":0,
            "network_broadcasts":0,
            "merchant_canary_passed":bool(getattr(settings,"MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED",False)),
            "accept_new_payments":bool(getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False)),
            "private_download_backend_ready":False,
            "existing_pending_invoices":None,
            "rotating_queue_importable":True,
            "status_routes_mounted":False,
            "scheduled_worker_installed_once":False}
    try:
        _paid_read_db(settings,connection)
        result["private_download_backend_ready"]=True
    except PaymentHold:
        pass
    pending=PaymentIntent.objects.filter(provider=PROVIDER,status=WAITING)
    result["existing_pending_invoices"]=pending.count()
    marker="/home/zomorod2/Saeit-staging/scripts/mpw_trx_commercial_reconcile_cron.py"
    result["scheduled_worker_file_exists"]=Path(marker).is_file()
    with_cursor=read_cursor(Path("/home/zomorod2/.local/share"))
    result["cursor_state_valid"]=isinstance(with_cursor,int)
    selected=pick_pending_page(PaymentIntent,PROVIDER,WAITING,with_cursor,limit=6)
    result["page_limited"]=len(selected)<=6
    result["selection_includes_only_outstanding"]=all(
        row.provider==PROVIDER and row.status==WAITING for row in selected)
    for route in ("/commerce/trx-easy/start/72/","/commerce/trx-easy/download/72/",
                  "/commerce/trx-easy/status/72/","/commerce/trx-easy/reconcile/72/"):
        match=resolve(route)
        if not callable(match.func):
            raise RuntimeError("Gated TRX route missing")
    result["status_routes_mounted"]=True
    proc=subprocess.run(["/usr/bin/crontab","-l"],stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,timeout=12,check=False)
    if proc.returncode==0:
        lines=[s for s in proc.stdout.decode("utf8","replace").splitlines()
               if "MPW_TRX_AUTORECONCILE_GUARDED_V1" in s]
        result["scheduled_worker_installed_once"]=len(lines)==1
    try:
        _commercial_db(settings,connection)
        result["release_gate_open"]=True
    except PaymentHold:
        result["release_gate_open"]=False
    return result

if __name__=="__main__":
    try:
        print("MPW_TRX_PRODUCTION_READINESS="+json.dumps(inspect(),sort_keys=True))
    except Exception as e:
        print("MPW_TRX_PRODUCTION_READINESS="+json.dumps({
            "status":"BLOCKED","reason_type":type(e).__name__,
            "financial_writes":0},sort_keys=True))
        raise SystemExit(2)
