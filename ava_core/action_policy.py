"""Fail-closed action authorization for the single mojtaba.bot.ai identity.

This is a pure decision module: it never executes an action or grants a
credential. The host must authenticate the principal and verify approval
receipts against its trusted ledger before calling authorize().
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class Action(str, Enum):
    READ_OWN_DATA = "read_own_data"
    LOCAL_DRAFT = "local_draft"
    SEND_MESSAGE = "send_message"
    PUBLISH = "publish"
    LIVE_TRADE = "live_trade"
    TRANSFER_FUNDS = "transfer_funds"
    CHANGE_ACCESS = "change_access"
    DELETE_DATA = "delete_data"
    DEPLOY = "deploy"


SENSITIVE = frozenset({
    Action.SEND_MESSAGE, Action.PUBLISH, Action.LIVE_TRADE,
    Action.TRANSFER_FUNDS, Action.CHANGE_ACCESS,
    Action.DELETE_DATA, Action.DEPLOY,
})


@dataclass(frozen=True)
class ActionRequest:
    owner_id: str
    action: Action
    resource_id: str
    authenticated: bool = False
    approved_action: Action | None = None
    approved_resource_id: str | None = None
    approval_verified: bool = False


def authorize(request: ActionRequest) -> Decision:
    """An approval applies to one exact action/resource, never a category.

    approval_verified is a claim made by the trusted host after checking the
    approval's issuer, expiry, revocation, identity and audit record. Untrusted
    user input must never be mapped to this flag.
    """
    if not isinstance(request, ActionRequest):
        return Decision.DENY
    # Host input is untrusted until validated. Truthy strings/integers are
    # not proof of authentication or of a verified owner approval.
    if (type(request.owner_id) is not str or not request.owner_id.strip()
            or type(request.resource_id) is not str or not request.resource_id.strip()):
        return Decision.DENY
    if not isinstance(request.action, Action):
        return Decision.DENY
    if request.authenticated is not True:
        return Decision.DENY
    if request.action not in SENSITIVE:
        return Decision.ALLOW
    if (
        request.approval_verified is True
        and request.approved_action is request.action
        and request.approved_resource_id == request.resource_id
    ):
        return Decision.ALLOW
    return Decision.REQUIRE_APPROVAL
