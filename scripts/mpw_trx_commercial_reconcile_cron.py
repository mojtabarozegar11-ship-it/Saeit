#!/usr/bin/env python3
"""Small, reentrant merchant-owned TRX auto-reconciliation cycle.

Run from a locked server cron; no wallet keys, no broadcasts, no user claims.
Disabled until independently verified and merchant-canary release flags exist.
Only already-paid, validated on-chain funds produce ledger/fulfillment writes.
"""
from __future__ import annotations
import json,os,sys
from datetime import timedelta
from pathlib import Path
ROOT=Path("/home/zomorod2/Saeit-staging")
if not ROOT.is_dir() or ROOT.is_symlink():
    raise SystemExit("Unexpected merchant runtime")
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")

def run_once():
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.utils import timezone
    from core.models import PaymentIntent
    from services.mpw_trx_walletless_core import PaymentHold
    from services.mpw_walletless_commercial_intent import (
        PROVIDER,WAITING,_commercial_db,reconcile_commercial_intent_from_candidates,
    )
    from services.mpw_tron_readonly_deposit_candidates import find_candidate_hashes
    from services.mpw_trx_commercial_chain import read_only_independent_pair

    result={"mode":"commercial-trx-automated-reconciliation",
            "public_checkout_activated":False,"examined":0,"settled":0,
            "pending":0,"held":0}
    try:
        _commercial_db(settings,connection)
    except PaymentHold:
        result["mode"]="NOT_RELEASED"
        return result
    result["public_checkout_activated"]=True
    # Review transfers within the immutable issued invoice window, even
    # when the browser has closed. A 36-hour lookback tolerates short outages.
    queued=list(PaymentIntent.objects.filter(
        provider=PROVIDER,status=WAITING,
        created_at__gte=timezone.now()-timedelta(hours=36),
    ).select_related("order").order_by("created_at")[:6])
    if not queued:
        return result
    try:
        pair=read_only_independent_pair()
    except (PaymentHold,OSError,ValueError):
        result["mode"]="RPC_UNAVAILABLE_FAIL_CLOSED"
        result["held"]=len(queued)
        return result
    for item in queued:
        result["examined"]+=1
        try:
            outcome=reconcile_commercial_intent_from_candidates(
                item.pk,item.order.customer_id,
                server_lookup=find_candidate_hashes,pair=pair,
            )
        except (PaymentHold,OSError,ValueError):
            result["held"]+=1
            continue
        if outcome=="paid":
            result["settled"]+=1
        else:
            result["pending"]+=1
    return result

if __name__=="__main__":
    try:
        print("MPW_TRX_AUTORECONCILE="+json.dumps(run_once(),sort_keys=True))
    except Exception as exc:
        # No private exception messages, no sensitive record IDs or tx hashes.
        print("MPW_TRX_AUTORECONCILE="+json.dumps({
            "mode":"FAIL_CLOSED","error_class":type(exc).__name__,
            "public_checkout_activated":False,
        },sort_keys=True))
        raise SystemExit(2)
