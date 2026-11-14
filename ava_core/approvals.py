"""Fail-closed, pure authorization boundary for mojtaba.bot.ai operations.

No credentials, network requests, or external actions are performed here.
The host must authenticate the principal and enforce the returned decision.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from .identity import BOT_ID

SENSITIVE_OPERATIONS = frozenset({
    "payment", "transfer", "live_trade", "send_message", "publish",
    "deploy", "delete_data", "change_access", "purchase", "legal_commitment",
})

@dataclass(frozen=True)
class Approval:
    owner_id: str
    operation: str
    resource_id: str
    expires_at: datetime
    approved: bool

def authorized(*, owner_id: str, operation: str, resource_id: str,
               approval: Approval | None, now: datetime | None = None) -> bool:
    """Return a decision only; host must independently authenticate and audit.

    Malformed or coerced values never constitute approval. This module neither
    consumes a receipt nor executes payments, messages, deployments or trades.
    """
    fields = (owner_id, operation, resource_id)
    if any(type(value) is not str or not value.strip() for value in fields):
        return False
    if operation not in SENSITIVE_OPERATIONS:
        return False
    if not isinstance(approval, Approval) or approval.approved is not True:
        return False
    verified_fields = (approval.owner_id, approval.operation, approval.resource_id)
    if any(type(value) is not str for value in verified_fields):
        return False
    if verified_fields != fields:
        return False
    timestamp = now if now is not None else datetime.now(timezone.utc)
    expiry = approval.expires_at
    if not isinstance(timestamp, datetime) or not isinstance(expiry, datetime):
        return False
    try:
        if timestamp.utcoffset() is None or expiry.utcoffset() is None:
            return False
        return timestamp < expiry
    except (TypeError, ValueError, OverflowError):
        return False
