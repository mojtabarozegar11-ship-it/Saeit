from dataclasses import dataclass
from typing import Any, Callable, Dict
import hashlib
import json

from django.db import transaction

from .agent_registry import AgentRegistry, RISK_ORDER
from .models import AgentTask, ApprovalGrant, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval
from .unified_bot_identity import BOT_CODE


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
            approved = ApprovalRequest.objects.filter(
                action_type=normalize_action(task.action_type),
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
    def _reserve_invocation(self, spec, task_id, execution_id, payload):
        """Reserve one external-capable tool call per execution before dispatch.

        Lock the AgentTask, recheck its policy and persist the invocation start
        in a short transaction. Never hold a DB lock across a tool handler: a
        handler might call an external provider or block indefinitely. A lost
        acknowledgement leaves the reservation in place, fail-closed.
        """
        if task_id is None or not str(execution_id or "").strip():
            raise ToolGatewayError(
                "A running task and execution identity are required for tool invocation"
            )
        try:
            AgentTask.objects.select_for_update().get(pk=task_id)
        except AgentTask.DoesNotExist as exc:
            raise ToolGatewayError("Agent task was not found") from exc

        task = self._authorize_execution(spec, task_id, execution_id)
        # Every entry from this gateway records execution_id in after_state.
        # Checking the execution, rather than just the tool name, also blocks
        # a second alias/adapter call under the same task execution.
        previous = AuditLog.objects.filter(
            action="tool_invocation_started",
            target_type="AgentTask",
            target_id=str(task.pk),
            after_state__execution_id=task.execution_id,
        ).exists()
        if previous:
            raise ToolGatewayError(
                "Tool invocation already reserved for this execution; "
                "receipt reconciliation is required before any retry"
            )

        # The canonical bot must have an actual single-use owner grant for
        # sensitive operations. An approved AgentTask request alone is not
        # authorization to repeat a payment, publication or deployment.
        # This check and grant consumption share the task-row transaction with
        # the invocation reservation. Never acquire a remote lock or dispatch
        # a provider call before this durable gate succeeds.
        sensitive = (
            requires_owner_approval(spec.code, spec.risk)
            or requires_owner_approval(task.action_type, task.risk_snapshot)
        )
        if task.agent.code == BOT_CODE and sensitive:
            task_input = task.input_data
            grant_id = (
                task_input.get("owner_approval_grant_id")
                if isinstance(task_input, dict) else None
            )
            if type(grant_id) is not int or grant_id <= 0:
                raise ToolGatewayError(
                    "Canonical sensitive operation requires an exact one-time owner grant"
                )
            grant = (
                ApprovalGrant.objects.select_for_update()
                .select_related("approval")
                .filter(pk=grant_id)
                .first()
            )
            if grant is None or (
                grant.approval.status != "approved"
                or grant.approval.action_type != normalize_action(task.action_type)
                or grant.approval.target_type != "AgentTask"
                or grant.approval.target_id != str(task.pk)
                or grant.actor_id != grant.approval.requested_by_id
            ):
                raise ToolGatewayError(
                    "Canonical sensitive operation grant has no matching owner approval"
                )
            # The grant also binds the exact planned parameters. The internal
            # grant id is never handed to the registered tool handler.
            if not isinstance(task.input_data, dict):
                raise ToolGatewayError(
                    "Canonical sensitive task input must be an object"
                )
            planned_payload = {
                key: value for key, value in task.input_data.items()
                if key != "owner_approval_grant_id"
            }
            if payload != planned_payload:
                raise ToolGatewayError(
                    "Canonical sensitive invocation differs from reviewed task payload"
                )
            try:
                packed = json.dumps(
                    planned_payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True, allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ToolGatewayError(
                    "Canonical sensitive task payload is not canonical JSON"
                ) from exc

            from .approval import ApprovalService

            required_scope = {
                "action": normalize_action(task.action_type),
                "agent_task_id": task.pk,
                "execution_id": task.execution_id,
                "tool_code": spec.code,
                "payload_sha256": hashlib.sha256(packed).hexdigest(),
            }
            try:
                ApprovalService().authorize_grant(grant_id, required_scope)
            except ValueError as exc:
                raise ToolGatewayError(
                    "Canonical sensitive operation grant is invalid, expired or consumed"
                ) from exc

        trace_id = f"tool-{task.pk}-{task.execution_id}-{spec.code}"
        AuditLog.objects.create(
            actor_type="agent",
            actor_id=str(task.agent_id),
            action="tool_invocation_started",
            target_type="AgentTask",
            target_id=str(task.pk),
            before_state={},
            after_state={
                "tool_code": spec.code,
                "risk": spec.risk,
                "execution_id": task.execution_id,
                "trace_id": trace_id,
            },
            trace_id=trace_id,
        )
        return task, trace_id

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

        # Do not forward the database authorization reference to any provider.
        # All other parameters remain unchanged for compatibility.
        dispatch_data = {
            key: value for key, value in data.items()
            if key != "owner_approval_grant_id"
        }
        task, trace_id = self._reserve_invocation(
            spec, task_id, execution_id, dispatch_data
        )

        try:
            result = spec.handler(dispatch_data)
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
