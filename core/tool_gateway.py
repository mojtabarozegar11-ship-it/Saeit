from dataclasses import dataclass
from typing import Any, Callable, Dict

from django.db import transaction

from .models import AgentTask, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval


class ToolGatewayError(ValueError):
    """Raised when a tool invocation violates the execution policy."""


@dataclass(frozen=True)
class ToolSpec:
    code: str
    handler: Callable[[dict], Any]
    risk: str = "low"
    enabled: bool = True


class ToolGateway:
    """Allowlisted tool boundary bound to an authenticated AgentTask execution."""

    def __init__(self, tools=None):
        self._tools: Dict[str, ToolSpec] = {}
        for spec in tools or []:
            self.register(spec)

    def register(self, spec: ToolSpec):
        code = normalize_action(spec.code)
        if not code:
            raise ToolGatewayError("Tool code is required")
        risk = normalize_risk(spec.risk)
        if not callable(spec.handler):
            raise ToolGatewayError("Tool handler must be callable")
        self._tools[code] = ToolSpec(
            code=code, handler=spec.handler, risk=risk, enabled=spec.enabled
        )

    def describe(self):
        return {
            code: {"risk": spec.risk, "enabled": spec.enabled}
            for code, spec in sorted(self._tools.items())
        }

    def _authorize_execution(self, spec, task_id, execution_id):
        if task_id is None or not str(execution_id or "").strip():
            raise ToolGatewayError(
                "A running task and execution identity are required for tool invocation"
            )

        try:
            task = AgentTask.objects.select_related("agent").get(pk=task_id)
        except AgentTask.DoesNotExist as exc:
            raise ToolGatewayError("Agent task was not found") from exc

        if task.status != "running":
            raise ToolGatewayError("Tool invocation requires a running task")
        if str(execution_id) != task.execution_id:
            raise ToolGatewayError(
                "Execution identity does not match the active task execution"
            )

        if requires_owner_approval(spec.code, spec.risk):
            approved = ApprovalRequest.objects.filter(
                target_type="AgentTask",
                target_id=str(task.pk),
                status="approved",
            ).exists()
            if not approved:
                raise ToolGatewayError(
                    "Owner approval is required before tool invocation"
                )

        return task

    @transaction.atomic
    def invoke(self, tool_code, payload=None, *, task_id=None, execution_id=None):
        code = normalize_action(tool_code)
        spec = self._tools.get(code)
        if not spec:
            raise ToolGatewayError("Tool is not registered")
        if not spec.enabled:
            raise ToolGatewayError("Tool is disabled")

        data = payload or {}
        if not isinstance(data, dict):
            raise ToolGatewayError("Tool payload must be an object")

        task = self._authorize_execution(spec, task_id, execution_id)
        trace_id = f"tool-{task.pk}-{task.execution_id}-{code}"
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action="tool_invocation_started",
            target_type="AgentTask",
            target_id=str(task.pk),
            before_state={},
            after_state={
                "tool_code": code,
                "risk": spec.risk,
                "execution_id": task.execution_id,
                "trace_id": trace_id,
            },
            trace_id=trace_id,
        )

        try:
            result = spec.handler(data)
        except Exception as exc:
            AuditLog.objects.create(
                actor_type="agent",
                actor_id=str(task.agent_id),
                action="tool_invocation_failed",
                target_type="AgentTask",
                target_id=str(task.pk),
                after_state={
                    "tool_code": code,
                    "execution_id": task.execution_id,
                    "error": str(exc)[:5000],
                    "trace_id": trace_id,
                },
                trace_id=trace_id,
            )
            raise

        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action="tool_invocation_completed",
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state={
                "tool_code": code,
                "execution_id": task.execution_id,
                "trace_id": trace_id,
            },
            trace_id=trace_id,
        )
        return result
