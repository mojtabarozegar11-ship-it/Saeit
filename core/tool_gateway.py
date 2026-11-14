from dataclasses import dataclass
from typing import Any, Callable, Dict

from django.core.exceptions import ImproperlyConfigured

from .agent_registry import AgentRegistry, RISK_ORDER
from .task_approval_scope import has_approved_task_request
from .canonical_bot_identity import is_master_only_action, resolve_single_active_agent
from .models import Agent, AgentTask, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval


class ToolGatewayError(ValueError):
    """Raised when a tool invocation violates the execution policy."""


@dataclass(frozen=True)
class ToolSpec:
    code: str
    handler: Callable[[dict], Any]
    risk: str = "low"
    enabled: bool = True
    # An action may call a differently named adapter only when the adapter
    # explicitly declares that alias. A worker's tool_map is not authority.
    allowed_actions: tuple[str, ...] = ()


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
        allowed_actions = tuple(
            dict.fromkeys(normalize_action(action) for action in (spec.allowed_actions or (code,)))
        )
        if any(not action for action in allowed_actions):
            raise ToolGatewayError("Allowed action codes must be non-empty")
        self._tools[code] = ToolSpec(
            code=code, handler=spec.handler, risk=risk, enabled=spec.enabled,
            allowed_actions=allowed_actions,
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

        if not task.agent.active:
            raise ToolGatewayError("Task agent is inactive")
        registry = AgentRegistry()
        capability = registry.capability_for(task.agent, task.action_type)
        if capability is None or (
            task.capability_code and task.capability_code != capability.code
        ):
            raise ToolGatewayError("Task capability has been revoked or changed")
        if normalize_action(task.action_type) not in spec.allowed_actions:
            raise ToolGatewayError("Tool is not authorized for this task action")
        if is_master_only_action(spec.code) or is_master_only_action(task.action_type):
            try:
                master = resolve_single_active_agent(Agent)
            except ImproperlyConfigured as exc:
                raise ToolGatewayError("MASTER_GATEWAY_MULTIPLE_ACTIVE_RUNTIMES") from exc
            if master is None or task.agent_id != master.pk:
                # A direct gateway invocation must not bypass worker identity.
                raise ToolGatewayError("MASTER_GATEWAY_NONCANONICAL_AGENT_BLOCKED")
        snapshot_risk = normalize_risk(task.risk_snapshot)
        if registry.effective_risk(capability, snapshot_risk) != snapshot_risk:
            raise ToolGatewayError("Task risk policy changed after planning")
        # A sensitive adapter cannot be smuggled into a low-risk task through
        # an alias. The task must first be planned at the higher risk.
        if (
            RISK_ORDER[spec.risk] > RISK_ORDER[snapshot_risk]
            and requires_owner_approval(spec.code, spec.risk)
        ):
            raise ToolGatewayError("Tool risk exceeds the approved task risk snapshot")

        if (
            requires_owner_approval(spec.code, spec.risk)
            or requires_owner_approval(task.action_type, snapshot_risk)
        ):
            if not has_approved_task_request(task, required_risk=snapshot_risk):
                raise ToolGatewayError(
                    "Owner approval is required before tool invocation"
                )

        return task

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
