from django.db import transaction
import uuid

from .agent_registry import AgentRegistry
from .models import AgentTask, ApprovalRequest, AuditLog
from .services import normalize_risk, requires_owner_approval


TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class TaskExecutionError(ValueError):
    """Raised when a task cannot safely enter execution."""


class TaskRuntime:
    """Controlled AgentTask lifecycle with final policy, identity, and retry gates."""

    @transaction.atomic
    def claim(self, task_id):
        task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
        if task.status != "queued":
            raise TaskExecutionError(f"Task is not executable from status: {task.status}")
        if not task.agent.active:
            raise TaskExecutionError("Task agent is inactive")

        registry = AgentRegistry()
        capability = registry.capability_for(task.agent, task.action_type)
        if not capability:
            raise TaskExecutionError("Task agent no longer has an active capability for this action")
        if task.capability_code and capability.code != task.capability_code:
            raise TaskExecutionError("Task capability policy no longer matches its execution snapshot")

        try:
            snapshot_risk = normalize_risk(task.risk_snapshot)
        except ValueError as exc:
            raise TaskExecutionError("Task risk snapshot is invalid") from exc
        effective_risk = registry.effective_risk(capability, snapshot_risk)
        if effective_risk != snapshot_risk:
            raise TaskExecutionError("Task risk policy has changed since planning")
        if requires_owner_approval(task.action_type, effective_risk):
            approved = ApprovalRequest.objects.filter(
                target_type="AgentTask", target_id=str(task.pk), status="approved"
            ).exists()
            if not approved:
                raise TaskExecutionError("Owner approval is required before execution")

        if task.attempt_count >= task.max_attempts:
            raise TaskExecutionError("Task retry budget exhausted")
        task.execution_id = uuid.uuid4().hex
        task.attempt_count += 1
        task.status = "running"
        task.save(update_fields=["execution_id", "attempt_count", "status", "updated_at"])
        self._audit(task, "task_claimed", {
            "status": "running",
            "action_type": task.action_type,
            "risk": effective_risk,
            "execution_id": task.execution_id,
            "attempt": task.attempt_count,
        })
        return task

    @transaction.atomic
    def complete(self, task_id, output_data=None, cost=0):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        task.output_data = output_data or {}
        task.cost = cost or 0
        task.status = "completed"
        task.save(update_fields=["output_data", "cost", "status", "updated_at"])
        self._audit(task, "task_completed", {"status": "completed", "execution_id": task.execution_id})
        return task

    @transaction.atomic
    def fail(self, task_id, error):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        task.output_data = {"error": str(error)[:5000]}
        task.status = "failed" if task.attempt_count >= task.max_attempts else "queued"
        task.save(update_fields=["output_data", "status", "updated_at"])
        self._audit(task, "task_failed", {
            "status": task.status,
            "error": str(error)[:5000],
            "execution_id": task.execution_id,
            "attempt": task.attempt_count,
        })
        return task

    def _audit(self, task, action, state):
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action=action,
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state=state,
            trace_id=f"task-{task.pk}-{task.execution_id or 'none'}",
        )
