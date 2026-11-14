"""Fail-closed action gate for the single mojtaba.bot.ai identity.

Pure logic only: never executes an action, transfers money, or grants access.
The host must authenticate the actor and verify approval independently.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

SENSITIVE = frozenset({
    'payment', 'trade_live', 'external_message', 'publish', 'deploy',
    'change_access', 'delete_data', 'legal_commitment', 'transfer_funds',
})

@dataclass(frozen=True)
class Approval:
    action: str
    resource: str
    expires_at: datetime
    verified: bool
    approval_id: str


def authorize(action: str, resource: str, approval: Approval | None = None,
              *, now: datetime | None = None) -> bool:
    """Pure allowlist decision, not an authorization receipt or execution."""
    if (type(action) is not str or not action.strip()
            or type(resource) is not str or not resource.strip()):
        return False
    if action not in SENSITIVE:
        return False
    if (not isinstance(approval, Approval) or approval.verified is not True
            or type(approval.approval_id) is not str
            or not approval.approval_id.strip()):
        return False
    if (type(approval.action) is not str or type(approval.resource) is not str
            or approval.action != action or approval.resource != resource):
        return False
    expiry = approval.expires_at
    instant = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(expiry, datetime) or not isinstance(instant, datetime):
        return False
    try:
        if expiry.utcoffset() is None or instant.utcoffset() is None:
            return False
        return instant < expiry
    except (TypeError, ValueError, OverflowError):
        return False
