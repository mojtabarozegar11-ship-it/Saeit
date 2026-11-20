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
    """Require exact, unexpired, case-sensitive, per-operation approval.

    Approval records MUST originate from a trusted authenticated host, never
    from model output or a user-supplied message. The host must atomically
    consume request_id before executing a sensitive operation to prevent replay.
    """
    if not authenticated or not all((owner_id, operation, resource_id, request_id)):
        return False
    if operation not in SENSITIVE:
        return False  # No implicit allowlist for unknown or ordinary operations.
    if approval is None:
        return False
    fields = ((approval.owner_id, owner_id), (approval.operation, operation),
              (approval.resource_id, resource_id), (approval.request_id, request_id))
    if not all(compare_digest(a, b) for a, b in fields):
        return False
    expiry = approval.expires_at
    if expiry.tzinfo is None:
        return False
    return expiry.astimezone(timezone.utc) > datetime.now(timezone.utc)
