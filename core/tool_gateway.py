from dataclasses import dataclass
from typing import Any, Callable, Dict

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
    """Allowlisted tool boundary. Tools are invoked only through registered specs."""

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
        self._tools[code] = ToolSpec(code=code, handler=spec.handler, risk=risk, enabled=spec.enabled)

    def describe(self):
        return {
            code: {"risk": spec.risk, "enabled": spec.enabled}
            for code, spec in sorted(self._tools.items())
        }

    def invoke(self, tool_code, payload=None, *, approved=False):
        code = normalize_action(tool_code)
        spec = self._tools.get(code)
        if not spec:
            raise ToolGatewayError("Tool is not registered")
        if not spec.enabled:
            raise ToolGatewayError("Tool is disabled")
        if requires_owner_approval(code, spec.risk) and not approved:
            raise ToolGatewayError("Owner approval is required before tool invocation")
        data = payload or {}
        if not isinstance(data, dict):
            raise ToolGatewayError("Tool payload must be an object")
        return spec.handler(data)
