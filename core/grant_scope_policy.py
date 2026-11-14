"""Immutable, allowlisted one-time approval-grant scopes for mojtaba.bot.ai.

This pure validation module does not authenticate the HTTP caller, consume a
grant, execute tools, send mail, spend money, or establish commercial revenue.
Its decisions must be enforced by ApprovalService in a DB transaction.
"""
from __future__ import annotations

import re


# No broad wildcard / freeform action: each supported scope has one exact shape.
_SCOPE_SCHEMAS = {
    "publish": ("KnowledgeArticle", frozenset({"action", "target"}), "high"),
    "payment": ("Order", frozenset({"action", "target"}), "critical"),
    "external_write": ("TradeEmailOutbox", frozenset({"action", "outbox_id", "message_digest"}), "high"),
    "knowledge_content_generation": (
        "AgentTask", frozenset({"action", "run_id", "paid_model"}), "high",
    ),
}
_DECIMAL_ID = re.compile(r"[1-9][0-9]{0,17}\Z")


def require_exact_grant_scope(approval, scope) -> dict:
    """Return a canonical copy or reject an action/target/risk escalation.

    An Approved request alone is NOT authority to mint unrelated grant actions.
    This function is deliberately independent of Django for quick review.
    """
    if type(scope) is not dict or type(getattr(approval, "action_type", None)) is not str:
        raise ValueError("GRANT_SCOPE_INVALID")
    action = scope.get("action")
    if type(action) is not str or action not in _SCOPE_SCHEMAS:
        raise ValueError("GRANT_ACTION_NOT_ALLOWLISTED")
    expected_type, expected_keys, min_risk = _SCOPE_SCHEMAS[action]
    if type(getattr(approval, "target_type", None)) is not str:
        raise ValueError("GRANT_APPROVAL_TARGET_INVALID")
    if (approval.action_type != action
            or approval.target_type != expected_type
            or set(scope) != expected_keys):
        raise ValueError("GRANT_APPROVAL_ACTION_OR_SCOPE_MISMATCH")
    target_id = getattr(approval, "target_id", None)
    if type(target_id) is not str or not target_id.strip() or len(target_id) > 100:
        raise ValueError("GRANT_APPROVAL_TARGET_ID_INVALID")
    risk = getattr(approval, "risk", None)
    risk_value = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(
        risk if type(risk) is str else ""
    )
    if risk_value is None or risk_value < {"high": 3, "critical": 4}[min_risk]:
        raise ValueError("GRANT_APPROVAL_RISK_INSUFFICIENT")

    if action in {"publish", "payment"}:
        if _DECIMAL_ID.fullmatch(target_id) is None:
            raise ValueError("GRANT_OBJECT_ID_INVALID")
        prefix = "knowledge" if action == "publish" else "order"
        if type(scope["target"]) is not str or scope["target"] != f"{prefix}:{target_id}":
            raise ValueError("GRANT_OBJECT_SCOPE_MISMATCH")
    elif action == "external_write":
        if (_DECIMAL_ID.fullmatch(target_id) is None
                or type(scope["outbox_id"]) is not int
                or scope["outbox_id"] != int(target_id)
                or type(scope["message_digest"]) is not str
                or re.fullmatch(r"[a-f0-9]{64}", scope["message_digest"]) is None):
            raise ValueError("GRANT_MAIL_SCOPE_NOT_BOUND_TO_ONE_MESSAGE")
    else:
        if (_DECIMAL_ID.fullmatch(target_id) is None
                or type(scope["run_id"]) is not int
                or scope["run_id"] < 1
                or scope["paid_model"] is not True):
            raise ValueError("GRANT_PAID_MODEL_SCOPE_INVALID")
    return dict(scope)


def require_exact_consumption_scope(saved_scope, required_scope) -> dict:
    """No prefix/subset match, wildcard, dict coercion or unbound consumption."""
    if type(saved_scope) is not dict or type(required_scope) is not dict:
        raise ValueError("GRANT_CONSUMPTION_SCOPE_MUST_BE_EXPLICIT")
    if not saved_scope or not required_scope:
        raise ValueError("GRANT_CONSUMPTION_SCOPE_MUST_BE_EXPLICIT")
    if set(saved_scope) != set(required_scope):
        raise ValueError("GRANT_SCOPE_MISMATCH")
    if any(type(saved_scope[k]) is not type(required_scope[k])
           or saved_scope[k] != required_scope[k] for k in saved_scope):
        raise ValueError("GRANT_SCOPE_MISMATCH")
    return dict(saved_scope)
