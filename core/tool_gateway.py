from dataclasses import dataclass
import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from typing import Any, Callable, Dict

from .models import AgentCapability, AgentTask, AgentToolGrant, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval
from .factory_contracts import (
    FactoryAgentOutput, GatewayAdapterReceipt, GatewayAuthorization, GatewayInvocation,
    GatewayToolAttestation, GatewayToolResult, canonical_digest, validate_task_intent,
)


class ToolGatewayError(ValueError):
    """Raised when a tool invocation violates the execution policy."""


_factory_invocations = set()
_factory_attestations = {}
_factory_adapter_receipts = {}


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
        lease_seconds = int(getattr(settings, "FACTORY_EXECUTION_LEASE_SECONDS", 900))
        if task.updated_at <= timezone.now() - timedelta(seconds=lease_seconds):
            raise ToolGatewayError("Task execution lease has expired")
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
        resource = self._resource(task, data)
        snapshot = task.prerequisite_snapshot if isinstance(task.prerequisite_snapshot, dict) else {}
        token = GatewayAuthorization(
            task_id=task.pk, agent_id=task.agent_id, execution_id=task.execution_id,
            tool_code=code, resource=resource, environment=task.environment,
            prerequisite_digest=str(snapshot.get("digest") or ""), nonce=object(),
        )
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
        if not isinstance(token, GatewayAuthorization) or token.nonce not in self._authorizations:
            return False
        try:
            current = AgentTask.objects.select_related("agent").get(pk=task.pk)
            code = normalize_action(tool_code)
            spec = self._tools.get(code)
            snapshot = current.prerequisite_snapshot if isinstance(current.prerequisite_snapshot, dict) else {}
            if (
                not spec or token.task_id != current.pk or token.agent_id != current.agent_id
                or token.execution_id != current.execution_id or token.tool_code != code
                or current.action_type != code or token.environment != current.environment
                or token.resource != self._resource(current, current.input_data or {})
                or token.prerequisite_digest != str(snapshot.get("digest") or "")
            ):
                return False
            self._authorize_execution(spec, current.pk, token.execution_id)
            self._authorize_factory_grant(current, code, current.input_data or {})
            if code.startswith("product_"):
                from .factory_governance import validate_task_prerequisites
                validate_task_prerequisites(current)
        except Exception:
            return False
        return True

    def execute_factory_adapter(self, executor, task, authorization):
        """Run the existing registered executor and mint a bound, one-use receipt."""
        from .factory_agent_runtime import FactoryAgentRuntime
        from .factory_governance import validate_task_prerequisites
        try:
            current = AgentTask.objects.select_related("agent", "factory_run", "product").get(pk=task.pk)
        except AgentTask.DoesNotExist as exc:
            raise ToolGatewayError("Factory task was not found") from exc
        if type(executor) is not FactoryAgentRuntime:
            self._authorizations.discard(getattr(authorization, "nonce", None))
            raise ToolGatewayError("The registered FactoryAgentRuntime is required to produce adapter output")
        if not self.is_authorized(authorization, current, current.action_type):
            self._authorizations.discard(getattr(authorization, "nonce", None))
            raise ToolGatewayError("Factory adapter authorization is expired or no longer valid")
        try:
            validate_task_intent(current.input_data or {})
            validate_task_prerequisites(current)
        except Exception:
            self._authorizations.discard(authorization.nonce)
            raise
        resource = self._resource(current, current.input_data or {})
        result = None
        try:
            result = executor.execute(
                current, authorization=authorization, authorization_check=self.is_authorized
            )
            if not self.is_authorized(authorization, current, current.action_type):
                raise ToolGatewayError("Factory adapter authorization expired before output could be accepted")
            validated = FactoryAgentOutput.validate(current.action_type, getattr(result, "values", None))
            if not isinstance(result, FactoryAgentOutput) or result.action != current.action_type:
                raise ToolGatewayError("Factory adapter returned output outside the registered contract")
            values = json.loads(json.dumps(validated.values, sort_keys=True, separators=(",", ":"), default=str))
            output_digest = canonical_digest(values)
            snapshot = current.prerequisite_snapshot if isinstance(current.prerequisite_snapshot, dict) else {}
            receipt = GatewayAdapterReceipt(
                task_id=current.pk, agent_id=current.agent_id, execution_id=current.execution_id,
                action=current.action_type, resource=resource, environment=current.environment,
                prerequisite_digest=str(snapshot.get("digest") or ""),
                output_digest=output_digest, values=values, nonce=object(),
            )
            context = (
                receipt.task_id, receipt.agent_id, receipt.execution_id, receipt.action,
                receipt.resource, receipt.environment, receipt.prerequisite_digest,
            )
            _factory_adapter_receipts[receipt.nonce] = (context, output_digest)
            return receipt
        finally:
            self._authorizations.discard(authorization.nonce)

    def invoke(self, tool_code, payload=None, *, task_id=None, execution_id=None, adapter_receipt=None, agent_output=None):
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
            if agent_output is not None:
                raise ToolGatewayError("A supplied FactoryAgentOutput cannot replace an executor receipt")
            try:
                validate_task_intent(task.input_data or {})
            except ValueError as exc:
                raise ToolGatewayError(str(exc)) from exc
            if data != task.input_data:
                raise ToolGatewayError("Factory payload must exactly match the persisted Task intent")
            from .factory_governance import validate_task_prerequisites
            try:
                validate_task_prerequisites(task)
            except Exception as exc:
                raise ToolGatewayError(f"Factory prerequisites are stale or invalid: {exc}") from exc
            snapshot = task.prerequisite_snapshot if isinstance(task.prerequisite_snapshot, dict) else {}
            expected_context = (
                task.pk, task.agent_id, task.execution_id, task.action_type,
                self._resource(task, data), task.environment, str(snapshot.get("digest") or ""),
            )
            if not isinstance(adapter_receipt, GatewayAdapterReceipt):
                raise ToolGatewayError("Factory tool invocation requires an executor-issued receipt")
            stored = _factory_adapter_receipts.pop(adapter_receipt.nonce, None)
            actual_context = (
                adapter_receipt.task_id, adapter_receipt.agent_id, adapter_receipt.execution_id,
                adapter_receipt.action, adapter_receipt.resource, adapter_receipt.environment,
                adapter_receipt.prerequisite_digest,
            )
            if (
                stored != (actual_context, adapter_receipt.output_digest)
                or actual_context != expected_context
                or adapter_receipt.output_digest != canonical_digest(adapter_receipt.values)
            ):
                raise ToolGatewayError("Factory executor receipt is forged, mutated, stale, or unrelated")
            try:
                output = FactoryAgentOutput.validate(task.action_type, adapter_receipt.values)
            except ValueError as exc:
                raise ToolGatewayError("Factory executor receipt output no longer satisfies its schema") from exc
            data = dict(data)
            data["__agent_output"] = output
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
