#!/usr/bin/env python3
"""Small, reentrant merchant-owned TRX auto-reconciliation cycle.

Run from a locked server cron; no wallet keys, no broadcasts, no user claims.
Reads only previously issued invoices when checkout is disabled. Never creates an order.
Only already-paid, validated on-chain funds produce ledger/fulfillment writes.
"""
from __future__ import annotations
import json,os,sys
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
    from core.models import PaymentIntent
    from services.mpw_trx_reconcile_cursor import (read_cursor,write_cursor,pick_pending_page)
    from services.mpw_trx_walletless_core import PaymentHold
    from services.mpw_walletless_commercial_intent import (
        PROVIDER,WAITING,_paid_read_db,reconcile_commercial_intent_from_candidates,public_release_authorized,
    )
    from services.mpw_tron_readonly_deposit_candidates import find_candidate_hashes
    from services.mpw_trx_commercial_chain import read_only_independent_pair

    result={"mode":"commercial-trx-automated-reconciliation",
            "public_checkout_activated":False,"examined":0,"settled":0,
            "pending":0,"held":0}
    try:
        _paid_read_db(settings,connection)
    except PaymentHold:
        result["mode"]="FINANCIAL_BACKEND_UNAVAILABLE"
        return result
    publish_allowed=bool(
        getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) and
        public_release_authorized(settings)
    )
    if publish_allowed:
        from services.mpw_trx_commercial_web import _configured_receiver
        from services.mpw_walletless_commercial_intent import require_active_merchant_wallet
        try:
            require_active_merchant_wallet(settings, _configured_receiver())
            result["public_checkout_activated"]=True
        except PaymentHold:
            result["public_checkout_activated"]=False
    # Publication permission is not proof of mainnet account activation.
    # All unpaid invoices must remain eligible after service downtime.
    # A rotating checkpoint prevents six old unresolved invoices from
    # starving all other buyers forever.
    home=Path("/home/zomorod2/.local/share")
    cursor=read_cursor(home)
    queued=pick_pending_page(PaymentIntent,PROVIDER,WAITING,cursor,limit=6)
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
    # Advance only AFTER the batch was attempted. A failed blockchain
    # transaction remains pending and will be retried on subsequent cycles.
    write_cursor(home,queued[-1].pk)
    return result

if __name__=="__main__":
    try:
        result = run_once()
        # Email outbox belongs to existing core.Order rows, independent of RPC availability.
        from services.mpw_trx_guest_delivery import flush_outbox
        try:
            result["guest_email_sent"] = flush_outbox()
        except Exception as mail_exc:
            result["guest_email_error_class"] = type(mail_exc).__name__
        print("MPW_TRX_AUTORECONCILE="+json.dumps(result,sort_keys=True))
    except Exception as exc:
        # No private exception messages, no sensitive record IDs or tx hashes.
        print("MPW_TRX_AUTORECONCILE="+json.dumps({
            "mode":"FAIL_CLOSED","error_class":type(exc).__name__,
            "public_checkout_activated":False,
        },sort_keys=True))
        raise SystemExit(2)
