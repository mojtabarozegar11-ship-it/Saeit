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
    """Require an exact, unexpired, affirmative approval for sensitive actions.

    Missing or malformed input denies. Approval does not perform an action.
    The caller must additionally validate the authenticated owner and persist
    an audit record before performing any approved external operation.
    """
    if not owner_id or not owner_id.strip() or not resource_id or not resource_id.strip():
        return False
    if not operation or not operation.strip():
        return False
    if operation not in SENSITIVE_OPERATIONS:
        return False  # No implicit grant for unknown operations.
    if approval is None or approval.approved is not True:
        return False
    if (approval.owner_id, approval.operation, approval.resource_id) != (
        owner_id, operation, resource_id
    ):
        return False
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or approval.expires_at.tzinfo is None:
        return False
    return timestamp < approval.expires_at
