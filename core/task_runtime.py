from decimal import Decimal, InvalidOperation
import uuid

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .agent_registry import AgentRegistry
from .models import AgentTask, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval
from .unified_bot_identity import BOT_CODE


TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class TaskExecutionError(ValueError):
    """Raised when a task cannot safely enter execution."""


class TaskRuntime:
    """Controlled AgentTask lifecycle with final policy, identity, and retry gates."""

    @transaction.atomic
    def claim(self, task_id):
        task = AgentTask.objects.select_for_update().select_related("agent", "project").get(pk=task_id)
        if task.status != "queued":
            if task.status == "failed" and task.attempt_count >= task.max_attempts:
                raise TaskExecutionError("Task retry budget exhausted")
            raise TaskExecutionError(f"Task is not executable from status: {task.status}")
        if not task.agent.active:
            raise TaskExecutionError("Task agent is inactive")

        # One execution owner across economic and factory lanes of Mojtaba.bot.ai.
        # On row-locking databases select_for_update also locks the joined
        # agent row, serializing claims of different tasks by this agent.
        if task.agent.code == BOT_CODE and AgentTask.objects.filter(
            agent_id=task.agent_id, status="running"
        ).exclude(pk=task.pk).exists():
            raise TaskExecutionError(
                "Unified economic executor already has a running task; wait for completion or recovery"
            )

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
            # A same-PK approval for another action (or another project's
            # owner) is not an execution authorization.
            approvals = ApprovalRequest.objects.filter(
                target_type="AgentTask",
                target_id=str(task.pk),
                action_type=normalize_action(task.action_type),
                status="approved",
            )
            if task.project_id:
                approvals = approvals.filter(requested_by_id=task.project.owner_id)
            if not approvals.exists():
                raise TaskExecutionError(
                    "Matching owner approval is required before execution"
                )

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
        if task.agent.code == BOT_CODE:
            # Even an exhausted retry budget does not prove an external side
            # effect failed. Preserve the prior execution identity for
            # reconciliation and never silently requeue or close the incident.
            task.status = "blocked"
            task.output_data = {
                "error": "Stale canonical execution requires effect reconciliation",
                "requires_review": True,
                "automatic_replay_allowed": False,
                "previous_execution_id": previous_execution_id,
                "retry_budget_exhausted": task.attempt_count >= task.max_attempts,
            }
        elif task.attempt_count >= task.max_attempts:
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
                "requires_review": task.status == "blocked",
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
        normalized_output = output_data or {}
        # Economic work is not complete merely because a handler returned. It must
        # prove an observable effect. This prevents report-only/no-op cycles from
        # being counted as operational progress.
        if (
            str(task.capability_code or "").startswith("income_")
            or task.capability_code == "master_self_improvement"
        ):
            if normalized_output.get("verified_effect") is not True:
                raise TaskExecutionError(
                    "Economic task cannot complete without verified_effect=true"
                )
            evidence = normalized_output.get("evidence")
            if not isinstance(evidence, dict) or not any(
                str(value or "").strip() for value in evidence.values()
            ):
                raise TaskExecutionError(
                    "Economic task cannot complete without concrete evidence"
                )
            action = str(normalized_output.get("action_performed") or "").strip()
            if not action:
                raise TaskExecutionError(
                    "Economic task cannot complete without action_performed"
                )
        task.output_data = normalized_output
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
        if task.agent.code == BOT_CODE:
            # The tool may have produced an external effect immediately before
            # failing or losing its acknowledgement. Without an independently
            # reconciled receipt an automatic retry is unsafe, regardless of
            # remaining attempts. Preserve the execution token for correlation.
            task.status = "blocked"
            task.output_data = {
                "error": str(error)[:5000],
                "requires_review": True,
                "automatic_replay_allowed": False,
                "previous_execution_id": previous_execution_id,
                "retry_budget_exhausted": task.attempt_count >= task.max_attempts,
            }
        else:
            task.output_data = {"error": str(error)[:5000]}
            if task.attempt_count >= task.max_attempts:
                task.status = "failed"
            else:
                # Preserve the pre-existing retry policy for noncanonical
                # workers until their external effects have been inventoried.
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
                "requires_review": task.status == "blocked",
                "automatic_replay_allowed": task.status == "queued",
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
