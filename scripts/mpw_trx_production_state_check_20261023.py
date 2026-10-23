#!/usr/bin/env python3
"""Privacy-preserving production TRX gateway diagnostic; strictly no writes."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
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
    # Confirm cron actually EXECUTED; a registered schedule alone proves little.
    logfile=Path("/home/zomorod2/.local/share/mpw-trx-reconcile.log")
    result["cron_recent_execution"]=False
    result["last_worker_mode"]="NO_RECENT_LOG"
    if logfile.is_file() and not logfile.is_symlink() and logfile.stat().st_size<2_000_000:
        result["cron_recent_execution"]=bool(
            0<=time.time()-logfile.stat().st_mtime<=240)
        if result["cron_recent_execution"]:
            for entry in reversed(logfile.read_text("utf8","replace").splitlines()[-30:]):
                if entry.startswith("MPW_TRX_AUTORECONCILE="):
                    try:
                        report=json.loads(entry.split("=",1)[1])
                        if isinstance(report,dict):
                            mode=str(report.get("mode","UNKNOWN"))
                            result["last_worker_mode"]=mode[:55]
                    except (ValueError,TypeError):
                        result["last_worker_mode"]="MALFORMED_WORKER_STATUS"
                    break
    # Verify merchant checkout dependencies read-only, without exposing
    # wallet address or current pricing to CI logs.
    try:
        from services.mpw_trx_commercial_web import _configured_receiver
        from scripts.mojplaywin_native_chain_verify import tron_address_to_hex
        recipient=_configured_receiver()
        tron_address_to_hex(recipient)
        result["merchant_native_trx_receiver_valid"]=True
    except Exception as exc:
        result["merchant_native_trx_receiver_valid"]=False
        result["receiver_error_type"]=type(exc).__name__
    try:
        from services.mpw_trx_commercial_web import _rate_provider
        from decimal import Decimal
        from django.utils import timezone
        rate,observed=_rate_provider()
        age=(timezone.now()-observed).total_seconds()
        result["new_trx_quote_valid"]=bool(
            Decimal(str(rate)).is_finite() and Decimal(str(rate))>0 and -15<=age<=120
        )
        result["quote_observation_recent"]=bool(-15<=age<=120)
    except Exception as exc:
        result["new_trx_quote_valid"]=False
        result["quote_error_type"]=type(exc).__name__
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
