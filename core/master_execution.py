"""Controlled execution engine for the Saeit Master Agent.

Turns goals into persisted AgentTask records, selects active agents by capability,
and enforces approval boundaries. Concrete external tool adapters can register
handlers without giving the language model unrestricted execution authority.
"""
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from django.db import transaction

from .models import Agent, AgentTask, ApprovalRequest, AuditLog

HIGH_RISK = {"high", "critical"}


@dataclass
class ExecutionResult:
    task_id: int
    status: str
    output: dict
    approval_id: int | None = None


class MasterExecutionEngine:
    handlers: dict[str, Callable] = {}

    @classmethod
    def register_handler(cls, capability_code: str, handler: Callable):
        cls.handlers[capability_code] = handler

    def select_agent(self, capability_code: str):
        return (
            Agent.objects.filter(active=True, capabilities__code=capability_code,
                                 capabilities__active=True)
            .order_by("risk_level", "id")
            .first()
        )

    @transaction.atomic
    def create_task(self, *, capability_code, input_data, project=None, action_type="execute"):
        agent = self.select_agent(capability_code)
        if agent is None:
            raise ValueError(f"No active agent for capability: {capability_code}")
        task = AgentTask.objects.create(
            agent=agent,
            project=project,
            action_type=action_type,
            capability_code=capability_code,
            risk_snapshot=agent.risk_level,
            execution_id=uuid4().hex,
            input_data=input_data,
            status="queued",
        )
        AuditLog.objects.create(
            actor_type="master_agent", actor_id="master",
            action="task_created", target_type="AgentTask", target_id=str(task.pk),
            after_state={"capability": capability_code, "status": "queued"},
            trace_id=task.execution_id,
        )
        return task

    def execute(self, task: AgentTask, *, owner=None):
        if task.status in {"succeeded", "cancelled"}:
            return ExecutionResult(task.pk, task.status, task.output_data)
        if task.risk_snapshot in HIGH_RISK:
            approval = ApprovalRequest.objects.filter(
                target_type="AgentTask", target_id=str(task.pk), status="approved"
            ).order_by("-created_at").first()
            if approval is None:
                pending = ApprovalRequest.objects.filter(
                    target_type="AgentTask", target_id=str(task.pk), status="pending"
                ).first()
                if pending is None:
                    if owner is None:
                        task.status = "awaiting_approval"
                        task.save(update_fields=["status", "updated_at"])
                        return ExecutionResult(task.pk, task.status, {}, None)
                    pending = ApprovalRequest.objects.create(
                        action_type=task.action_type, target_type="AgentTask",
                        target_id=str(task.pk), reason="High-risk Master Agent execution",
                        risk=task.risk_snapshot, requested_by=owner,
                    )
                task.status = "awaiting_approval"
                task.save(update_fields=["status", "updated_at"])
                return ExecutionResult(task.pk, task.status, {}, pending.pk)

        handler = self.handlers.get(task.capability_code)
        if handler is None:
            task.status = "blocked"
            task.output_data = {"error": "No execution adapter registered"}
            task.save(update_fields=["status", "output_data", "updated_at"])
            return ExecutionResult(task.pk, task.status, task.output_data)

        task.status = "running"
        task.attempt_count += 1
        task.save(update_fields=["status", "attempt_count", "updated_at"])
        try:
            output = handler(task.input_data, task=task)
            task.output_data = output if isinstance(output, dict) else {"result": output}
            task.status = "succeeded"
        except Exception as exc:
            task.output_data = {"error": str(exc)}
            task.status = "queued" if task.attempt_count < task.max_attempts else "failed"
        task.save(update_fields=["status", "output_data", "updated_at"])
        AuditLog.objects.create(
            actor_type="master_agent", actor_id="master", action="task_execution",
            target_type="AgentTask", target_id=str(task.pk),
            after_state={"status": task.status, "attempt": task.attempt_count},
            trace_id=task.execution_id,
        )
        return ExecutionResult(task.pk, task.status, task.output_data)

    def run_queued(self, limit=20, *, owner=None):
        results = []
        for task in AgentTask.objects.filter(status="queued").order_by("created_at")[:limit]:
            results.append(self.execute(task, owner=owner))
        return results
