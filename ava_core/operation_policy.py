"""Fail-closed authorization boundary for mojtaba.bot.ai internal modules.

This module does not execute operations or grant permissions. It only decides
whether a proposed operation is eligible for execution by an authenticated host.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest

SENSITIVE = frozenset({
    "send_message", "publish", "deploy", "trade_live", "transfer_funds",
    "pay", "purchase", "change_access", "delete_data", "create_commitment",
    "enable_live_payment", "publish_signal",
})

@dataclass(frozen=True)
class Approval:
    owner_id: str
    operation: str
    resource_id: str
    request_id: str
    expires_at: datetime

def authorize(*, owner_id: str, operation: str, resource_id: str,
              request_id: str, authenticated: bool, approval: Approval | None) -> bool:
    """Require exact per-request approval; the host must atomically consume it.

    A pure decision is never proof of one-time consumption or external effect.
    """
    fields = (owner_id, operation, resource_id, request_id)
    if authenticated is not True or any(
        type(value) is not str or not value.strip() or len(value) > 512
        for value in fields
    ):
        return False
    if operation not in SENSITIVE or not isinstance(approval, Approval):
        return False
    approved_fields = (
        approval.owner_id, approval.operation, approval.resource_id,
        approval.request_id,
    )
    if any(type(value) is not str or len(value) > 512 for value in approved_fields):
        return False
    # Encode before constant-time comparison: hmac.compare_digest rejects
    # non-ASCII str, but valid owner/resource identifiers may be Unicode.
    if not all(
        compare_digest(a.encode("utf-8"), b.encode("utf-8"))
        for a, b in zip(approved_fields, fields)
    ):
        return False
    expiry = approval.expires_at
    if not isinstance(expiry, datetime):
        return False
    try:
        if expiry.utcoffset() is None:
            return False
        return expiry.astimezone(timezone.utc) > datetime.now(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return False
