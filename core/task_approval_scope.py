"""Strict binding of an owner's approval to one exact task and its risk.

An approval for another action or a lower-risk action never grants authority
to queue, claim or invoke a sensitive task. This module authorizes no execution.
"""
from .agent_registry import RISK_ORDER
from .models import ApprovalRequest
from .services import normalize_action, normalize_risk


def approval_covers_task(approval, task, *, required_risk=None):
    """Return False for mismatched or malformed approval scope (fail closed)."""
    if (approval.target_type != "AgentTask"
            or approval.target_id != str(task.pk)
            or normalize_action(approval.action_type) != normalize_action(task.action_type)):
        return False
    try:
        task_risk = normalize_risk(
            task.risk_snapshot if required_risk is None else required_risk
        )
        authorized_risk = normalize_risk(approval.risk)
    except ValueError:
        return False
    return RISK_ORDER[authorized_risk] >= RISK_ORDER[task_risk]


def has_approved_task_request(task, *, required_risk=None):
    """Never reuse an approved request from another action, task or risk tier."""
    requests = ApprovalRequest.objects.filter(
        target_type="AgentTask", target_id=str(task.pk), status="approved",
    )
    return any(approval_covers_task(
        request, task, required_risk=required_risk,
    ) for request in requests)
