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
    """Return True only for nonsensitive operations or exact valid approvals.

    True is not a command to execute; downstream enforcement remains required.
    """
    if not action or not resource or not action.strip() or not resource.strip():
        return False
    if action not in SENSITIVE:
        return False  # Unknown actions are denied until explicitly classified.
    if approval is None or not approval.verified or not approval.approval_id.strip():
        return False
    if approval.action != action or approval.resource != resource:
        return False
    if approval.expires_at.tzinfo is None:
        return False
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None:
        return False
    return instant < approval.expires_at
