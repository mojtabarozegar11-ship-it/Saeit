"""Read-only reconciliation dossier from existing Django task and audit rows.

This is a triage view, NOT independent evidence that an external side effect
did or did not occur. It never retries, unblocks, settles, or marks a job done.
"""
from __future__ import annotations

from .models import AgentTask, ApprovalRequest, AuditLog
from .unified_bot_identity import EXECUTOR_RUNTIME_CODES

RELEVANT_AUDIT_ACTIONS = frozenset({
    "task_claimed", "task_completed", "task_failed",
    "task_recovered_stale", "tool_invocation_started",
    "tool_invocation_completed", "tool_invocation_failed",
    "task_reconciliation_observation_recorded",
})
MAX_AUDIT_EVENTS = 100


def reconciliation_candidate(task: AgentTask) -> bool:
    output = task.output_data if isinstance(task.output_data, dict) else {}
    return (
        task.agent.code in EXECUTOR_RUNTIME_CODES
        and task.status in {"blocked", "failed"}
        and task.attempt_count > 0
        and output.get("requires_review") is True
    )


def build_reconciliation_dossier(task: AgentTask) -> dict:
    """Return bounded, non-sensitive metadata only; no provider calls."""
    if not reconciliation_candidate(task):
        raise ValueError("TASK_NOT_ELIGIBLE_FOR_UNCERTAIN_EFFECT_REVIEW")

    output = task.output_data if isinstance(task.output_data, dict) else {}
    execution_id = output.get("previous_execution_id") or task.execution_id
    if not isinstance(execution_id, str) or not 0 < len(execution_id) <= 64:
        # An unverifiable execution identity is itself a reconciliation gap.
        execution_id = None

    events = AuditLog.objects.filter(
        target_type="AgentTask",
        target_id=str(task.pk),
        action__in=RELEVANT_AUDIT_ACTIONS,
    ).order_by("-created_at", "-pk")[:MAX_AUDIT_EVENTS]

    receipts = []
    for event in events:
        state = event.after_state if isinstance(event.after_state, dict) else {}
        recorded_execution = state.get("execution_id") or state.get("previous_execution_id")
        receipts.append({
            "audit_id": event.pk,
            "event_type": event.action,
            "recorded_at": event.created_at.isoformat(),
            "same_execution_as_task": bool(
                execution_id is not None and recorded_execution == execution_id
            ),
        })

    approval_rows = ApprovalRequest.objects.filter(
        target_type="AgentTask", target_id=str(task.pk),
    )
    return {
        "task_id": task.pk,
        "action_type": task.action_type,
        "capability_code": task.capability_code,
        "agent_code": task.agent.code,
        "status": task.status,
        "attempt_count": task.attempt_count,
        "execution_id_recorded": execution_id is not None,
        "previous_execution_id": execution_id,
        "requires_review": True,
        "automatic_replay_allowed": False,
        "local_audit_receipts": receipts,
        "local_audit_receipts_capped": len(receipts) == MAX_AUDIT_EVENTS,
        "approval_record_counts": {
            "pending": approval_rows.filter(status="pending").count(),
            "approved": approval_rows.filter(status="approved").count(),
            "rejected": approval_rows.filter(status="rejected").count(),
        },
        "external_side_effect_status": "unknown",
        "independent_evidence_verified": False,
        "operator_action_required": (
            "Inspect independent host/provider outcome records before deciding "
            "whether and how to close or supersede this task."
        ),
        "replay_or_queue_transition_performed": False,
    }
