"""Fail-closed expiration policy for immutable MOJ PROP invoice settlement.

This module is deliberately isolated from production. A caller MUST evaluate it
inside the isolated database transaction with an authoritative locked invoice,
not a client-supplied timestamp. This guard does not settle a transaction.
"""
from datetime import datetime, timezone


class InvoiceExpiredOrInvalid(ValueError):
    """Invoice is expired or has untrustworthy timestamps/state."""


def require_unexpired_invoice(*, issued_at: datetime, expires_at: datetime,
                              status: str, now: datetime | None = None) -> None:
    """Reject malformed, expired, future-issued or non-awaiting invoices.

    Expiry is exclusive: settlement at exactly expires_at is rejected. Callers
    must also enforce immutable amount/version, single-use txid, chain finality,
    and atomic database transitions before granting any entitlement.
    """
    instant = datetime.now(timezone.utc) if now is None else now
    for value in (issued_at, expires_at, instant):
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise InvoiceExpiredOrInvalid("timezone-aware authoritative timestamps required")
    if type(status) is not str or status != "awaiting":
        raise InvoiceExpiredOrInvalid("invoice not awaiting settlement")
    if issued_at > instant or expires_at <= issued_at or instant >= expires_at:
        raise InvoiceExpiredOrInvalid("invoice outside valid settlement window")
