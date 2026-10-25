"""Bounded automatic TRX reconciliation with independently verified proof callbacks.

Scanner results supply transaction IDs ONLY, and never count as payment proof.
Both confirmation adapters must be pinned independent SolidityNode providers,
and must reconstruct full native TRX transfer body and execution receipt.
This test-focused module does not create a background scheduler or connect live.
"""
from datetime import datetime,timezone,timedelta
from typing import Callable
import re
from services.mpw_trx_walletless_core import PaymentHold,SolidifiedTransfer
from services.mpw_trx_walletless_finalize import (
    settle_isolated,candidates_for_auto_reconcile
)
from services.mpw_trx_walletless_smart_policy import (
    decide_candidate_next_step,advise_recheck,
)

TX_HASH=re.compile(r"^[a-f0-9]{64}$")


def reconcile_queued_invoices(
    conn,
    *,
    lookup_tx_candidates:Callable,
    independent_solidity_a:Callable,
    independent_solidity_b:Callable,
    sources_authenticated:bool,
    legacy_tx_used:Callable,
    now:datetime,
    max_items:int=25,
):
    """Scan once (e.g., by every-minute job); never trust user-supplied txid.

    No invoice is paid unless precisely one candidate matched its exact amount,
    destination and issued/expires time, then both trusted providers return
    full solidified transfer proofs and database atomic settlement succeeds.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise PaymentHold("UTC scan timestamp required")
    if not callable(lookup_tx_candidates) or not callable(independent_solidity_a) or not callable(independent_solidity_b):
        raise PaymentHold("Missing independent blockchain adapters")
    if sources_authenticated is not True or not callable(legacy_tx_used):
        raise PaymentHold("No approved two-source verification")
    rows=candidates_for_auto_reconcile(conn,max_items=max_items)
    stats={"pending":len(rows),"confirmed":0,"unmatched":0,"ambiguous":0,"held":0}
    if not rows:
        followup=advise_recheck(stats)
        stats["safe_next_action"]=followup.code
        stats["suggested_scan_after_seconds"]=followup.retry_after_seconds
        stats["requires_review"]=followup.requires_review
        return stats
    all_candidates=lookup_tx_candidates()
    if not isinstance(all_candidates,(list,tuple)) or len(all_candidates)>1000:
        raise PaymentHold("Unbounded indexer response")
    candidates=[]
    for e in all_candidates:
        # Indexer entries are only transaction references, not finality evidence.
        if (type(e) is not dict or type(e.get("tx_hash")) is not str
            or not TX_HASH.fullmatch(e["tx_hash"])
            or type(e.get("amount_sun")) is not int or e["amount_sun"]<=0
            or type(e.get("recipient")) is not str
            or not isinstance(e.get("block_time"),datetime)
            or e["block_time"].tzinfo is None):
            continue
        candidates.append(e)
    used_ids=set()
    for invoice_id,network,recipient,sun,issued,expires in rows:
        start=issued.replace(tzinfo=timezone.utc)
        end=expires.replace(tzinfo=timezone.utc)
        next_step=decide_candidate_next_step(
            recipient=recipient,amount_sun=int(sun),issued_at=start,expires_at=end,
            candidates=candidates,already_used=used_ids)
        if next_step.code=="await_exact_transfer":
            stats["unmatched"]+=1
            continue
        if next_step.code=="ambiguous_transfer_hold":
            stats["ambiguous"]+=1
            continue
        if next_step.code!="verify_dual_solidified_proof" or not next_step.txid:
            stats["held"]+=1
            continue
        tx=next_step.txid
        try:
            a=independent_solidity_a(tx)
            b=independent_solidity_b(tx)
            if not isinstance(a,SolidifiedTransfer) or not isinstance(b,SolidifiedTransfer):
                raise PaymentHold("Independent proof unavailable")
            result=settle_isolated(conn,int(invoice_id),a,b,
                legacy_tx_used=legacy_tx_used,sources_authenticated=True)
            if result!="paid":raise PaymentHold("Unexpected settlement result")
            used_ids.add(tx)
            stats["confirmed"]+=1
        except Exception:
            # A failed proof cannot create partial grants; settlement rolls back.
            stats["held"]+=1
    followup=advise_recheck(stats)
    stats["safe_next_action"]=followup.code
    stats["suggested_scan_after_seconds"]=followup.retry_after_seconds
    stats["requires_review"]=followup.requires_review
    return stats
