"""Reconcile only known pre-effect failures in the existing economic lane.

No broad retries, new agents, direct tool calls or live work at import time.
A replacement prerequisite is persisted before the old attempt is superseded;
both records and original error are preserved. Unknown outcomes need review.
"""
from django.db import transaction

from core.agent_registry import AgentRegistry
from core.economic_owner import economic_owner_code, economic_queue
from core.models import Agent, AgentTask, AuditLog
from core.services import requires_owner_approval

PRECONDITIONS = {
    ("income_mvp_build", "No designed offer exists; run income_offer_design first."): "income_offer_design",
    ("income_growth_experiment", "No built MVP exists; run income_mvp_build first."): "income_mvp_build",
}


@transaction.atomic
def reconcile_economic_precondition(*, task_id, agent_id, previous_attempt_count, error, tool_specs):
    if type(error) is not ValueError:
        return "review_unknown_error"
    agent = Agent.objects.select_for_update().filter(pk=agent_id, active=True).first()
    if agent is None or agent.code != economic_owner_code():
        return "review_owner_changed"
    task = economic_queue(agent.code).select_for_update().filter(pk=task_id, agent=agent).first()
    if task is None:
        return "review_task_missing"
    expected = PRECONDITIONS.get((task.action_type, str(error)))
    if (expected is None or task.capability_code != task.action_type
            or not isinstance(task.output_data, dict) or task.output_data.get("error") != str(error)):
        return "review_unverified_precondition"
    if (task.status != "queued" or task.execution_id or task.cost != 0
            or task.attempt_count != previous_attempt_count + 1
            or task.attempt_count >= task.max_attempts):
        return "review_task_state_changed_or_exhausted"
    if requires_owner_approval(task.action_type, task.risk_snapshot):
        return "review_original_approval_required"
    spec = tool_specs.get(expected, {})
    capability = agent.capabilities.filter(code=expected, active=True).first()
    if capability is None or spec.get("enabled") is not True or "risk" not in spec:
        return "review_prerequisite_unavailable"
    risk = AgentRegistry().effective_risk(capability, spec["risk"])
    if requires_owner_approval(expected, risk):
        return "review_prerequisite_approval_required"
    pending = list(economic_queue(agent.code).select_for_update().filter(
        agent=agent, status__in=("queued", "running", "blocked")).exclude(pk=task.pk)[:2])
    if pending:
        if len(pending) != 1:
            return "review_other_pending_work"
        replacement = pending[0]
        if (replacement.action_type != expected or replacement.capability_code != expected
                or replacement.project_id != task.project_id or replacement.status != "queued"
                or replacement.execution_id or replacement.attempt_count != 0
                or replacement.max_attempts <= 0 or replacement.cost != 0
                or replacement.risk_snapshot != risk):
            return "review_other_pending_work"
        created = False
    else:
        replacement = AgentTask.objects.create(
            agent=agent, project_id=task.project_id, action_type=expected,
            capability_code=expected, risk_snapshot=risk,
            input_data={"objective": agent.mission, "replanned_from": task.pk,
                        "reason_code": "verified_missing_internal_precondition"},
            status="queued")
        created = True
    # Only known pre-effect failure can be superseded; never delete a task.
    task.output_data = {**task.output_data, "replanned_to": expected,
                        "replacement_task_id": replacement.pk, "replan_created": created}
    task.status = "cancelled"
    task.save(update_fields=["status", "output_data", "updated_at"])
    AuditLog.objects.create(
        actor_type="agent", actor_id=str(agent.pk), action="economic_precondition_reconciled",
        target_type="AgentTask", target_id=str(task.pk), trace_id=f"economic-replan-{task.pk}-{task.attempt_count}",
        after_state={"prerequisite": expected, "replacement_task_id": replacement.pk,
                     "created": created, "external_effect_verified": False})
    return "prerequisite_ready"
