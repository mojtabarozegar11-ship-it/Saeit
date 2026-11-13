"""Fail-closed scope validation for the one existing Django chat approval path.

The planner emits advisory typed requests. Only a separately authorized owner
may approve and explicitly execute them. Legacy unbound approvals are rejected
until reconciled; this module does not issue credentials or perform actions.
"""
import json
import re

from .chat_operation_security import is_authorized_chat_operator
from .models import ChatSession

EXPECTED = {
    "cpanel.preflight": ("cPanel", "medium", frozenset()),
    "cpanel.passenger_inventory": ("cPanel", "medium", frozenset()),
    "cpanel.deploy_release": ("cPanel", "critical", frozenset()),
    "site.create_draft_page": ("site", "high", frozenset(("path", "title", "body"))),
    "site.update_draft_page": ("site", "high", frozenset(("path", "instruction"))),
}
SITES = frozenset(("zomorodmelal", "mojplaywin"))


def validate_chat_operation_scope(approval):
    """Return an immutable-in-intent parsed scope for the claimed approval."""
    if (approval.target_type != "ChatOperation"
            or not is_authorized_chat_operator(approval.requested_by)):
        raise PermissionError("CHAT_OPERATION_CANONICAL_OWNER_REQUIRED")
    raw = approval.reason
    if not isinstance(raw, str) or not 0 < len(raw) <= 10000:
        raise ValueError("CHAT_OPERATION_REASON_INVALID")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("CHAT_OPERATION_REASON_INVALID_JSON") from exc
    if not isinstance(data, dict) or set(data) != {
            "operation_id", "action", "target", "parameters", "session_id"}:
        raise ValueError("CHAT_OPERATION_SCOPE_INVALID")
    operation_id, action = data["operation_id"], data["action"]
    if not isinstance(operation_id, str) or re.fullmatch(r"[a-f0-9]{32}", operation_id) is None:
        raise ValueError("CHAT_OPERATION_ID_INVALID")
    if approval.target_id != operation_id or action not in EXPECTED:
        raise ValueError("CHAT_OPERATION_ID_OR_ACTION_MISMATCH")
    target_rule, risk, expected_params = EXPECTED[action]
    if approval.action_type != "chat:" + action or approval.risk != risk:
        raise ValueError("CHAT_OPERATION_ACTION_RISK_MISMATCH")
    session_id = data["session_id"]
    if type(session_id) is not int or session_id <= 0:
        raise ValueError("CHAT_OPERATION_SESSION_INVALID")
    if not ChatSession.objects.filter(
            pk=session_id, user_id=approval.requested_by_id, status="active").exists():
        raise PermissionError("CHAT_OPERATION_SESSION_OWNER_MISMATCH")
    params, target = data["parameters"], data["target"]
    if not isinstance(params, dict) or set(params) != expected_params:
        raise ValueError("CHAT_OPERATION_PARAMETERS_INVALID")
    if target_rule == "cPanel":
        if target != "cPanel":
            raise ValueError("CHAT_OPERATION_TARGET_INVALID")
    else:
        if target not in SITES:
            raise ValueError("CHAT_OPERATION_SITE_TARGET_INVALID")
        path = params["path"]
        if (not isinstance(path, str) or not path.startswith("/")
                or len(path) > 180 or "\x00" in path or
                "//" in path or any(part == ".." for part in path.split("/"))):
            raise ValueError("CHAT_OPERATION_PATH_INVALID")
        if action == "site.create_draft_page":
            if (not isinstance(params["title"], str) or
                    not 0 < len(params["title"].strip()) <= 200 or
                    not isinstance(params["body"], str) or len(params["body"]) > 4000):
                raise ValueError("CHAT_OPERATION_DRAFT_INVALID")
        elif (not isinstance(params["instruction"], str) or
                not 0 < len(params["instruction"].strip()) <= 4000):
            raise ValueError("CHAT_OPERATION_INSTRUCTION_INVALID")
    return data
