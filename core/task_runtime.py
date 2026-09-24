from django.db import transaction

from .models import AgentTask, AuditLog


TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


class TaskExecutionError(ValueError):
    """Raised when a task cannot safely enter execution."""


class TaskRuntime:
    """Controlled AgentTask lifecycle; execution is never allowed from blocked state."""

    @transaction.atomic
    def claim(self, task_id):
        task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
        if task.status != "queued":
            raise TaskExecutionError(f"Task is not executable from status: {task.status}")
        if not task.agent.active:
            raise TaskExecutionError("Task agent is inactive")
        task.status = "running"
        task.save(update_fields=["status", "updated_at"])
        self._audit(task, "task_claimed", {"status": "running"})
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
        self._audit(task, "task_completed", {"status": "completed"})
        return task

    @transaction.atomic
    def fail(self, task_id, error):
        task = AgentTask.objects.select_for_update().get(pk=task_id)
        if task.status != "running":
            raise TaskExecutionError(f"Task is not running: {task.status}")
        task.output_data = {"error": str(error)[:5000]}
        task.status = "failed"
        task.save(update_fields=["output_data", "status", "updated_at"])
        self._audit(task, "task_failed", {"status": "failed", "error": str(error)[:5000]})
        return task

    def _audit(self, task, action, state):
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action=action,
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state=state,
            trace_id=f"task-{task.pk}",
        )
