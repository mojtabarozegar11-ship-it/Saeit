from decimal import Decimal, InvalidOperation
import uuid

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

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
            raise TaskExecutionError("Task risk policy has changed since planning; owner approval is required before execution")
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
    def heartbeat(self, task_id, execution_id=None):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError(
                "Execution identity does not match the active task execution"
            )
        task.save(update_fields=["updated_at"])
        return task

    @transaction.atomic
    def recover_stale(self, task_id, stale_after_seconds=900):
        try:
            seconds = int(stale_after_seconds)
        except (TypeError, ValueError) as exc:
            raise TaskExecutionError("stale_after_seconds must be an integer") from exc
        if seconds <= 0:
            raise TaskExecutionError("stale_after_seconds must be positive")

        task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")

        cutoff = timezone.now() - timedelta(seconds=seconds)
        if task.updated_at > cutoff:
            raise TaskExecutionError("Task execution is not stale")

        previous_execution_id = task.execution_id
        if task.attempt_count >= task.max_attempts:
            task.status = "failed"
            task.output_data = {
                "error": "Execution became stale and retry budget was exhausted"
            }
        else:
            task.status = "queued"
            task.execution_id = ""
            task.output_data = {
                "error": "Execution became stale and was re-queued for recovery"
            }

        task.save(
            update_fields=["status", "execution_id", "output_data", "updated_at"]
        )
        self._audit(
            task,
            "task_recovered_stale",
            {
                "status": task.status,
                "previous_execution_id": previous_execution_id,
                "attempt": task.attempt_count,
                "stale_after_seconds": seconds,
            },
            trace_execution_id=previous_execution_id,
        )
        return task

    @transaction.atomic
    def complete(self, task_id, output_data=None, cost=0, execution_id=None):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError("Execution identity does not match the active task execution")
        if not isinstance(output_data or {}, dict):
            raise TaskExecutionError("Task output must be an object")
        try:
            normalized_cost = Decimal(str(cost if cost is not None else "0"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise TaskExecutionError("Task cost is invalid") from exc
        if not normalized_cost.is_finite():
            raise TaskExecutionError("Task cost must be finite")
        if normalized_cost < 0:
            raise TaskExecutionError("Task cost cannot be negative")
        task.output_data = output_data or {}
        task.cost = normalized_cost
        task.status = "completed"
        task.save(update_fields=["output_data", "cost", "status", "updated_at"])
        self._audit(task, "task_completed", {"status": "completed", "execution_id": task.execution_id})
        return task

    @transaction.atomic
    def fail(self, task_id, error, execution_id=None):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        if not execution_id or execution_id != task.execution_id:
            raise TaskExecutionError("Execution identity does not match the active task execution")
        if not str(error or "").strip():
            raise TaskExecutionError("Task failure reason is required")
        previous_execution_id = task.execution_id
        task.output_data = {"error": str(error)[:5000]}
        if task.attempt_count >= task.max_attempts:
            task.status = "failed"
        else:
            # Invalidate the previous worker identity before the retry is claimable.
            task.execution_id = ""
            task.status = "queued"
        task.save(update_fields=["output_data", "execution_id", "status", "updated_at"])
        self._audit(
            task,
            "task_failed",
            {
                "status": task.status,
                "error": str(error)[:5000],
                "execution_id": task.execution_id,
                "previous_execution_id": previous_execution_id,
                "attempt": task.attempt_count,
            },
            trace_execution_id=previous_execution_id,
        )
        return task

    def _audit(self, task, action, state, trace_execution_id=None):
        trace_execution_id = trace_execution_id or task.execution_id or "none"
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action=action,
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state=state,
            trace_id=f"task-{task.pk}-{trace_execution_id}",
        )
