from decimal import Decimal, InvalidOperation
from typing import Mapping, Optional

from .services import normalize_action
from .task_runtime import TaskExecutionError, TaskRuntime
from .tool_gateway import ToolGateway, ToolGatewayError


class WorkerRunnerError(ValueError):
    """Raised when a worker cannot safely execute an AgentTask."""


class WorkerRunner:
    """Synchronous worker loop for one AgentTask execution.

    Queue/worker infrastructure can call this service repeatedly. The runner never
    bypasses TaskRuntime or ToolGateway, so claim, identity, approval, and retry
    policy remain centralized.
    """

    def __init__(
        self,
        gateway: ToolGateway,
        runtime: Optional[TaskRuntime] = None,
        tool_map: Optional[Mapping[str, str]] = None,
    ):
        self.gateway = gateway
        self.runtime = runtime or TaskRuntime()
        self.tool_map = {
            normalize_action(action): normalize_action(tool)
            for action, tool in (tool_map or {}).items()
        }

    def run(self, task_id):
        task = self.runtime.claim(task_id)
        execution_id = task.execution_id
        try:
            self.runtime.heartbeat(task.pk, execution_id=execution_id)
            tool_code = self._resolve_tool(task.action_type)
            payload = task.input_data or {}
            if not isinstance(payload, dict):
                raise WorkerRunnerError("Task input must be an object")

            result = self.gateway.invoke(
                tool_code,
                payload,
                task_id=task.pk,
                execution_id=execution_id,
            )
            output, cost = self._normalize_result(result)
            completed = self.runtime.complete(
                task.pk,
                output_data=output,
                cost=cost,
                execution_id=execution_id,
            )
            return completed
        except Exception as exc:
            try:
                self.runtime.fail(
                    task.pk,
                    str(exc)[:5000],
                    execution_id=execution_id,
                )
            except TaskExecutionError:
                # Preserve the original worker failure; a concurrent recovery or
                # lifecycle transition must not mask it.
                pass
            raise

    def _resolve_tool(self, action_type):
        action = normalize_action(action_type)
        if not action:
            raise WorkerRunnerError("Task action_type is required")
        tool_code = self.tool_map.get(action, action)
        if not tool_code:
            raise WorkerRunnerError("No tool is mapped to the task action")
        return tool_code

    @staticmethod
    def _normalize_result(result):
        if result is None:
            return {}, Decimal("0")
        if isinstance(result, dict):
            data = dict(result)
            raw_cost = data.pop("__cost", Decimal("0"))
            try:
                cost = Decimal(str(raw_cost))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise WorkerRunnerError("Tool result cost is invalid") from exc
            if not cost.is_finite() or cost < 0:
                raise WorkerRunnerError("Tool result cost must be finite and non-negative")
            return data, cost
        return {"result": result}, Decimal("0")
