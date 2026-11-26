"""Invoice time-window policy shared by the prospective versioned settlement path.

This module does not authorize a payment or mutate an invoice. The caller must
hold the authoritative invoice row lock, verify two independent finalized
on-chain proofs including the block timestamp, and enforce unique txid and
single-use retry redemption in one isolated DB transaction.
"""
from datetime import datetime, timezone


class InvoiceExpiredOrInvalid(ValueError):
    """Invoice is expired or has untrustworthy timestamps/state."""


def _aware(value: datetime) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def require_unexpired_invoice(*, issued_at: datetime, expires_at: datetime,
                              status: str, now: datetime | None = None) -> None:
    """Pre-issuance/pending-invoice check; NOT the finalized-transfer settle gate.

    This intentionally rejects a pending invoice after expiry. Do not invoke
    it to reject a finalized transfer that was mined within the invoice window.
    """
    instant = datetime.now(timezone.utc) if now is None else now
    if not all(_aware(v) for v in (issued_at, expires_at, instant)):
        raise InvoiceExpiredOrInvalid("timezone-aware authoritative timestamps required")
    if type(status) is not str or status != "awaiting":
        raise InvoiceExpiredOrInvalid("invoice not awaiting settlement")
    if issued_at > instant or expires_at <= issued_at or instant >= expires_at:
        raise InvoiceExpiredOrInvalid("invoice outside valid pending window")


def require_finalized_transfer_in_invoice_window(
    *, issued_at: datetime, expires_at: datetime, transfer_block_time: datetime,
    status: str, now: datetime | None = None,
) -> None:
    """Allow delayed finality only for an independently proven in-window transfer.

    Expiry is exclusive at the block timestamp. Both awaiting and expired
    states can be considered, but a manually/administratively expired invoice
    must be rejected by the caller unless an explicit, audited reconciliation
    authorization exists. Never infer chain finality from this pure function.
    """
    instant = datetime.now(timezone.utc) if now is None else now
    if not all(_aware(v) for v in (issued_at, expires_at, transfer_block_time, instant)):
        raise InvoiceExpiredOrInvalid("timezone-aware authoritative timestamps required")
    if type(status) is not str or status not in ("awaiting", "expired"):
        raise InvoiceExpiredOrInvalid("invoice not eligible for settlement")
    if expires_at <= issued_at or issued_at > instant:
        raise InvoiceExpiredOrInvalid("invalid invoice time window")
    if transfer_block_time > instant:
        raise InvoiceExpiredOrInvalid("future chain timestamp")
    if not (issued_at <= transfer_block_time < expires_at):
        raise InvoiceExpiredOrInvalid("transfer outside invoice time window")
