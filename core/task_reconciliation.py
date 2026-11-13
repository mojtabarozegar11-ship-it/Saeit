"""Read-only reconciliation dossier from existing Django task and audit rows.

This is a triage view, NOT independent evidence that an external side effect
did or did not occur. It never retries, unblocks, settles, or marks a job done.
"""
from __future__ import annotations

import re
from django.db import transaction
from .chat_operation_security import is_authorized_chat_operator

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

# A human-attached hash is a claim about an external artifact, not proof that
# the referenced artifact exists or establishes that no side effect occurred.
OBSERVATION_KINDS = frozenset({
    "host_process_record", "payment_provider_reference",
    "broker_order_reference", "game_event_ledger",
    "factory_receipt", "other_independent_record",
})
OBSERVED_DISPOSITIONS = frozenset({
    "owner_observed_effect", "owner_observed_no_effect", "still_unknown",
})


@transaction.atomic
def record_reconciliation_observation(
    task_id, *, actor, evidence_sha256, source_kind, disposition,
):
    """Append one owner observation, preserving the blocked/failed task state.

    This does NOT attest the external evidence, reconcile money or enable
    retries. An independent verifier and explicit non-replay closure design
    are still required before a task may be superseded.
    """
    if not is_authorized_chat_operator(actor):
        raise PermissionError("RECONCILIATION_OWNER_REQUIRED")
    if not isinstance(source_kind, str) or source_kind not in OBSERVATION_KINDS:
        raise ValueError("RECONCILIATION_EVIDENCE_SOURCE_INVALID")
    if not isinstance(disposition, str) or disposition not in OBSERVED_DISPOSITIONS:
        raise ValueError("RECONCILIATION_OBSERVATION_INVALID")
    if not isinstance(evidence_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", evidence_sha256
    ) or evidence_sha256 == "0" * 64:
        raise ValueError("RECONCILIATION_EVIDENCE_DIGEST_INVALID")

    task = AgentTask.objects.select_for_update().select_related(
        "agent", "project"
    ).get(pk=task_id)
    if task.project_id and task.project.owner_id != actor.pk:
        raise PermissionError("RECONCILIATION_PROJECT_OWNER_MISMATCH")
    if not reconciliation_candidate(task):
        raise ValueError("RECONCILIATION_TASK_NOT_REVIEWABLE")

    output = task.output_data if isinstance(task.output_data, dict) else {}
    execution_id = output.get("previous_execution_id") or task.execution_id
    if not isinstance(execution_id, str) or not re.fullmatch(
        r"[a-f0-9]{32}", execution_id
    ):
        raise ValueError("RECONCILIATION_EXECUTION_ID_NOT_ATTESTED")

    # Serialized by the existing task row; no parallel audit write for this
    # task may create the same observation through this method.
    duplicate = AuditLog.objects.filter(
        action="task_reconciliation_observation_recorded",
        target_type="AgentTask",
        target_id=str(task.pk),
        after_state__execution_id=execution_id,
        after_state__evidence_sha256=evidence_sha256,
    ).exists()
    if duplicate:
        raise ValueError("RECONCILIATION_DUPLICATE_OBSERVATION")

    event = AuditLog.objects.create(
        actor_type="owner_reconciliation_observation",
        actor_id=str(actor.pk),
        action="task_reconciliation_observation_recorded",
        target_type="AgentTask",
        target_id=str(task.pk),
        trace_id=f"task-{task.pk}-{execution_id}",
        before_state={},
        after_state={
            "execution_id": execution_id,
            "evidence_sha256": evidence_sha256,
            "source_kind": source_kind,
            "disposition": disposition,
            "independent_evidence_verified": False,
            "external_effect_status": "unknown",
            "task_status_preserved": task.status,
            "replay_allowed": False,
        },
    )
    return {
        "status": "owner_observation_recorded_only",
        "task_id": task.pk,
        "audit_id": event.pk,
        "task_status": task.status,
        "independent_evidence_verified": False,
        "automatic_replay_allowed": False,
        "payment_or_delivery_attested": False,
    }
