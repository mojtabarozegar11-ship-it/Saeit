"""Deterministic, fail-closed TRX reconciliation triage.

No model, wallet callback, browser data or transfer indexer may authorize money.
Automated reasoning here is restricted to which SAFE next step to try.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Collection, Mapping

from services.mpw_trx_walletless_core import PaymentHold


@dataclass(frozen=True)
class PaymentNextStep:
    code: str
    txid: str | None
    retry_after_seconds: int | None
    requires_review: bool


def decide_candidate_next_step(*, recipient: str, amount_sun: int,
                               issued_at: datetime, expires_at: datetime,
                               candidates: Collection[Mapping], already_used: set[str]):
    """Choose verification/retry/review, never buyer attribution or settlement.

    A differently sized payment to a shared merchant address cannot be tied to
    an invoice without independently authenticated buyer identity. Therefore
    under/over-payments are not automatically assigned, refunded or credited.
    """
    if (not isinstance(recipient,str) or type(amount_sun) is not int
        or amount_sun<=0 or not isinstance(candidates,(list,tuple))
        or not isinstance(already_used,set)):
        raise PaymentHold("Invalid reconciliation triage inputs")
    if (not isinstance(issued_at,datetime) or not isinstance(expires_at,datetime)
        or issued_at.tzinfo is None or expires_at.tzinfo is None
        or issued_at>=expires_at):
        raise PaymentHold("Invalid invoice bounds")
    start=issued_at.astimezone(timezone.utc)
    end=expires_at.astimezone(timezone.utc)
    matches={event["tx_hash"] for event in candidates
             if event["recipient"]==recipient and event["amount_sun"]==amount_sun
             and start<=event["block_time"].astimezone(timezone.utc)<=end}
    if not matches:
        return PaymentNextStep("await_exact_transfer",None,20,False)
    if len(matches)>1:
        return PaymentNextStep("ambiguous_transfer_hold",None,None,True)
    txid=next(iter(matches))
    if txid in already_used:
        return PaymentNextStep("reused_reference_hold",None,None,True)
    return PaymentNextStep("verify_dual_solidified_proof",txid,None,False)


def advise_recheck(stats: Mapping[str,int])->PaymentNextStep:
    """Operator/scheduler guidance only; never a refund or payment instruction."""
    for key in ("pending","confirmed","unmatched","ambiguous","held"):
        if type(stats.get(key)) is not int or stats[key]<0:
            raise PaymentHold("Invalid settlement statistics")
    if stats["ambiguous"]:
        return PaymentNextStep("manual_ambiguity_review",None,15,True)
    if stats["held"]:
        return PaymentNextStep("retry_or_review_proof_hold",None,15,True)
    if stats["unmatched"]:
        return PaymentNextStep("continue_safe_chain_scan",None,20,False)
    if stats["confirmed"]:
        return PaymentNextStep("rescan_for_remaining_orders",None,20,False)
    return PaymentNextStep("idle_no_pending_orders",None,60,False)
