"""Economic-only execution boundary, independent of the native factory ABI.

The VPS factory has its own receipt-bearing ToolGateway/WorkerRunner contract.
Economic work must never replace or reuse that executable contract merely to
run database-local research, draft preparation, or private evidence checks.
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction

from .agent_registry import AgentRegistry, RISK_ORDER
from .models import AgentTask, ApprovalRequest, AuditLog
from .services import normalize_action, normalize_risk, requires_owner_approval
from .task_runtime import TaskExecutionError, TaskRuntime


class EconomicExecutionError(ValueError):
    """Economic task lacks authorization or violates its zero-cost policy."""


class EconomicGateway:
    """Allowlisted internal economic tools with authenticated task identity."""

    def __init__(self, tools):
        self._tools = {}
        for code, risk, handler in tools:
            normalized = normalize_action(code)
            if not normalized or not (
                normalized.startswith("income_") or normalized == "master_self_improvement"
            ):
                raise EconomicExecutionError("Only economic tool codes may be registered")
            if not callable(handler) or normalized in self._tools:
                raise EconomicExecutionError("Economic tool must have one callable handler")
            self._tools[normalized] = (normalize_risk(risk), handler)

    def describe(self):
        return {code: {"risk": risk, "enabled": True} for code, (risk, _) in sorted(self._tools.items())}

    def invoke(self, tool_code, payload, *, task_id, execution_id):
        code = normalize_action(tool_code)
        spec = self._tools.get(code)
        if spec is None:
            raise EconomicExecutionError("Unregistered economic action")
        if not isinstance(payload, dict):
            raise EconomicExecutionError("Economic task input must be an object")
        if not execution_id:
            raise EconomicExecutionError("Task execution identity is required")

        with transaction.atomic():
            task = AgentTask.objects.select_for_update().select_related("agent").get(pk=task_id)
            if (task.status != "running" or task.execution_id != execution_id
                    or not task.agent.active or task.agent.code != "economic-master-agent"):
                raise EconomicExecutionError("Economic task is not the authorized active execution")
            if task.action_type != code or task.capability_code != code:
                raise EconomicExecutionError("Economic tool does not match task capability")
            registry = AgentRegistry()
            capability = registry.capability_for(task.agent, code)
            if capability is None:
                raise EconomicExecutionError("Economic capability has been revoked")
            risk, handler = spec
            snapshot = normalize_risk(task.risk_snapshot)
            if registry.effective_risk(capability, snapshot) != snapshot:
                raise EconomicExecutionError("Economic task risk policy changed")
            if RISK_ORDER[risk] > RISK_ORDER[snapshot]:
                raise EconomicExecutionError("Economic tool risk exceeds task snapshot")
            if requires_owner_approval(code, risk) or requires_owner_approval(code, snapshot):
                if not ApprovalRequest.objects.filter(
                    target_type="AgentTask", target_id=str(task.pk),
                    action_type=code, status="approved",
                ).exists():
                    raise EconomicExecutionError("Owner approval required for this economic task")

            trace = f"economic-{task.pk}-{execution_id}-{code}"
            AuditLog.objects.create(
                actor_type="agent", actor_id=str(task.agent_id),
                action="economic_tool_invocation_started", target_type="AgentTask",
                target_id=str(task.pk), after_state={"tool_code": code}, trace_id=trace,
            )
            # Deliberately no outbound adapter, factory attestation, payment,
            # wallet, message, or arbitrary action dispatch is reachable here.
            result = handler(payload)
            if not isinstance(result, dict):
                raise EconomicExecutionError("Economic handler must return evidence")
            output = dict(result)
            try:
                cost = Decimal(str(output.pop("__cost", "0")))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise EconomicExecutionError("Invalid economic cost") from exc
            if not cost.is_finite() or cost != 0:
                raise EconomicExecutionError("Economic tasks must not create financial cost")
            if (output.get("verified_effect") is not True
                    or not str(output.get("action_performed") or "").strip()
                    or not isinstance(output.get("evidence"), dict)
                    or not any(str(v or "").strip() for v in output["evidence"].values())):
                raise EconomicExecutionError("Economic execution requires concrete internal evidence")
            AuditLog.objects.create(
                actor_type="agent", actor_id=str(task.agent_id),
                action="economic_tool_invocation_completed", target_type="AgentTask",
                target_id=str(task.pk), after_state={"tool_code": code}, trace_id=trace,
            )
            return output


class EconomicWorkerRunner:
    """Use TaskRuntime for lifecycle, never the installed factory WorkerRunner."""

    def __init__(self, gateway, runtime=None):
        self.gateway = gateway
        self.runtime = runtime or TaskRuntime()

    def run(self, task_id):
        candidate = AgentTask.objects.select_related("agent").get(pk=task_id)
        if (candidate.agent.code != "economic-master-agent"
                or candidate.action_type not in self.gateway.describe()):
            raise EconomicExecutionError("Task is not eligible for the economic executor")
        task = self.runtime.claim(task_id)
        execution_id = task.execution_id
        try:
            self.runtime.heartbeat(task.pk, execution_id=execution_id)
            if not isinstance(task.input_data or {}, dict):
                raise EconomicExecutionError("Economic task input must be an object")
            with transaction.atomic():
                output = self.gateway.invoke(
                    task.action_type, task.input_data or {},
                    task_id=task.pk, execution_id=execution_id,
                )
                return self.runtime.complete(
                    task.pk, output_data=output, cost=Decimal("0"),
                    execution_id=execution_id,
                )
        except Exception as exc:
            try:
                self.runtime.fail(task.pk, type(exc).__name__, execution_id=execution_id)
            except TaskExecutionError:
                pass
            raise
