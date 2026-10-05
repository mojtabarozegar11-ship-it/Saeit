from dataclasses import dataclass
from django.conf import settings
from django.utils import timezone
from typing import Any, Callable, Dict

from .models import AgentCapability, AgentTask, AgentToolGrant, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval
from .factory_contracts import (
    FactoryAgentOutput, GatewayAuthorization, GatewayInvocation,
    GatewayToolAttestation, GatewayToolResult, validate_task_intent,
)


class ToolGatewayError(ValueError):
    """Raised when a tool invocation violates the execution policy."""


_factory_invocations = set()
_factory_attestations = {}


def consume_factory_invocation(payload, action):
    token = payload.get("__gateway_invocation") if isinstance(payload, dict) else None
    if (
        not isinstance(token, GatewayInvocation)
        or token.tool_code != action
        or token.nonce not in _factory_invocations
    ):
        raise ToolGatewayError("Factory effects must be invoked through the authorized ToolGateway.")
    _factory_invocations.remove(token.nonce)
    return True


def consume_factory_attestation(attestation, task):
    if not isinstance(attestation, GatewayToolAttestation):
        raise ToolGatewayError("Factory task completion requires a ToolGateway attestation.")
    stored = _factory_attestations.pop(attestation.nonce, None)
    if (
        stored != attestation
        or attestation.task_id != task.pk
        or attestation.execution_id != task.execution_id
        or attestation.tool_code != task.action_type
    ):
        raise ToolGatewayError("Factory ToolGateway attestation is invalid, stale, or unrelated.")
    return True


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
        self._authorizations = set()
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
        if not task.agent.active:
            raise ToolGatewayError("Inactive Agents cannot invoke tools")
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

    @staticmethod
    def _resource(task, payload):
        product_id = task.product_id or task.input_data.get("product_id") or payload.get("product_id")
        return f"product:{product_id}" if product_id else "product:new"

    def _authorize_factory_grant(self, task, code, payload):
        is_factory = (
            str(task.capability_code or "").startswith("product_")
            or str(task.action_type or "").startswith("product_")
        )
        if not is_factory:
            return
        try:
            validate_task_intent(task.input_data or {})
        except ValueError as exc:
            raise ToolGatewayError(str(exc)) from exc
        if (
            not str(task.capability_code or "").startswith("product_")
            or task.action_type != task.capability_code
            or code != task.capability_code
        ):
            raise ToolGatewayError("Factory task, capability, and tool must match exactly")
        if not AgentCapability.objects.filter(code=task.capability_code, active=True, agents__pk=task.agent_id).exists():
            raise ToolGatewayError("The assigned Agent no longer holds the active capability")
        environment = str(getattr(settings, "FACTORY_ENVIRONMENT", "development"))
        if task.environment != environment:
            raise ToolGatewayError("Task environment does not match the trusted execution environment")
        resource = self._resource(task, payload)
        grants = AgentToolGrant.objects.filter(
            agent_id=task.agent_id, capability_code=task.capability_code,
            tool_code=code, environment=environment, active=True,
            revoked_at__isnull=True,
        )
        allowed = any(
            (grant.valid_until is not None and grant.valid_until > timezone.now())
            and (grant.resource_scope == resource or
            (grant.resource_scope.endswith(":*") and resource.startswith(grant.resource_scope[:-1])))
            for grant in grants
        )
        if not allowed:
            raise ToolGatewayError("No effective Agent × capability × tool × resource × environment grant")

    def authorize(self, tool_code, payload=None, *, task_id=None, execution_id=None):
        """Authorize a Factory invocation before its adapter can call providers or write files."""
        code = normalize_action(tool_code)
        spec = self._tools.get(code)
        if not spec or not spec.enabled:
            raise ToolGatewayError("Tool is not registered or is disabled")
        data = payload or {}
        if not isinstance(data, dict):
            raise ToolGatewayError("Tool payload must be an object")
        task = self._authorize_execution(spec, task_id, execution_id)
        self._authorize_factory_grant(task, code, data)
        if (
            str(task.capability_code or "").startswith("product_")
            or str(task.action_type or "").startswith("product_")
        ):
            from .factory_governance import validate_task_prerequisites
            try:
                validate_task_prerequisites(task)
            except Exception as exc:
                raise ToolGatewayError(f"Factory prerequisites are stale or invalid: {exc}") from exc
        token = GatewayAuthorization(task_id=task.pk, execution_id=task.execution_id, tool_code=code, nonce=object())
        self._authorizations.add(token.nonce)
        trace_id = f"tool-{task.pk}-{task.execution_id}-{code}"
        AuditLog.objects.create(
            actor_type="agent", actor_id=str(task.agent_id),
            action="tool_invocation_authorized", target_type="AgentTask",
            target_id=str(task.pk), before_state={},
            after_state={"tool_code": code, "execution_id": task.execution_id,
                         "environment": task.environment, "trace_id": trace_id},
            trace_id=trace_id,
        )
        return token

    def is_authorized(self, token, task, tool_code):
        basic = (
            isinstance(token, GatewayAuthorization)
            and token.nonce in self._authorizations
            and token.task_id == task.pk
            and token.execution_id == task.execution_id
            and token.tool_code == normalize_action(tool_code)
        )
        if not basic:
            return False
        try:
            current = AgentTask.objects.get(pk=task.pk)
            spec = self._tools.get(token.tool_code)
            self._authorize_execution(spec, current.pk, current.execution_id)
            self._authorize_factory_grant(current, token.tool_code, current.input_data or {})
        except Exception:
            return False
        return True

    def invoke(self, tool_code, payload=None, *, task_id=None, execution_id=None, agent_output=None):
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
        self._authorize_factory_grant(task, code, data)
        factory_task = (
            str(task.capability_code or "").startswith("product_")
            or str(task.action_type or "").startswith("product_")
        )
        if factory_task:
            if not isinstance(agent_output, FactoryAgentOutput) or agent_output.action != task.action_type:
                raise ToolGatewayError("Factory output must be typed and match the authorized task action")
            data = dict(data)
            data["__agent_output"] = agent_output
        data = dict(data)
        invocation = None
        if factory_task:
            invocation = GatewayInvocation(
                task_id=task.pk, execution_id=task.execution_id, tool_code=code, nonce=object()
            )
            _factory_invocations.add(invocation.nonce)
            data["__gateway_invocation"] = invocation
        if task.product_id:
            data["product_id"] = task.product_id
        if task.factory_run_id:
            data["__run_id"] = task.factory_run.run_id
        data["__task_id"] = task.pk
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
            if invocation is not None:
                _factory_invocations.discard(invocation.nonce)
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
        if factory_task:
            attestation = GatewayToolAttestation(
                task_id=task.pk, execution_id=task.execution_id,
                tool_code=code, nonce=object(),
            )
            _factory_attestations[attestation.nonce] = attestation
            return GatewayToolResult(result=result, attestation=attestation)
        return result
