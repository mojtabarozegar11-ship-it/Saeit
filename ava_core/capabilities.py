"""One owner-scoped capability bus for mojtaba.bot.ai.

All external integrations are host-injected adapters inside the *same* bot.
The language model cannot create credentials or authorize its own effects.
No adapter is connected by importing this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from types import MappingProxyType
from typing import Callable, Mapping, Protocol

from .identity import validate_owner_id


_EFFECTS = frozenset({"local", "read", "write", "financial", "destructive", "physical"})


def _freeze_arguments(value: object) -> object:
    """Snapshot JSON-shaped action data so the approved request cannot drift."""
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Action argument keys must be strings")
        return MappingProxyType({key: _freeze_arguments(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_arguments(item) for item in value)
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise TypeError("Action arguments must be JSON-compatible data")


@dataclass(frozen=True)
class OperationSpec:
    name: str
    effect: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Operation name is required")
        if self.effect not in _EFFECTS:
            raise ValueError("Operation effect must be explicitly classified")


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    operations: tuple[OperationSpec, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Capability name is required")
        if not isinstance(self.operations, tuple) or not self.operations:
            raise ValueError("Capability must declare its operations")
        if not all(isinstance(op, OperationSpec) for op in self.operations):
            raise TypeError("Operations must be typed OperationSpec objects")
        names = [op.name for op in self.operations]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate operation names")


@dataclass(frozen=True)
class ActionRequest:
    request_id: str
    owner_id: str
    capability: str
    operation: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        for value in (self.request_id, self.owner_id, self.capability, self.operation):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Action identity fields must be nonempty strings")
        validate_owner_id(self.owner_id)
        if not isinstance(self.arguments, Mapping):
            raise TypeError("Action arguments must be a mapping")
        object.__setattr__(self, "arguments", _freeze_arguments(self.arguments))


@dataclass(frozen=True)
class AdapterResult:
    """An adapter's declared outcome, not independent proof of real-world success."""

    success: bool
    detail: str
    evidence_reference: str | None = None

    def __post_init__(self) -> None:
        if type(self.success) is not bool or not isinstance(self.detail, str) or not self.detail.strip():
            raise ValueError("Adapter must give a typed outcome and detail")
        if self.evidence_reference is not None and (
            not isinstance(self.evidence_reference, str) or not self.evidence_reference.strip()
        ):
            raise ValueError("Evidence reference must be nonempty when supplied")


@dataclass(frozen=True)
class ActionReceipt:
    request_id: str
    owner_id: str
    capability: str
    operation: str
    effect: str
    result: AdapterResult
    created_at: str
    independently_verified: bool = False


class CapabilityAdapter(Protocol):
    def __call__(self, request: ActionRequest) -> AdapterResult: ...


class CapabilityHub:
    """One namespace for modules: never starts another bot or background worker.

    Registration comes from the authenticated host. Nonlocal effects require a
    host decision for that exact request. Request IDs cannot be reused within
    one running instance, including when an adapter raises after side effects.
    An external persistent idempotency ledger is needed before production use.
    """

    def __init__(self, *, owner_id: str,
                 authorize: Callable[[str, ActionRequest, OperationSpec], bool] | None = None) -> None:
        validate_owner_id(owner_id)
        if authorize is not None and not callable(authorize):
            raise TypeError("authorize must be callable")
        self.owner_id = owner_id
        self._authorize = authorize
        self._adapters: dict[str, tuple[CapabilitySpec, CapabilityAdapter]] = {}
        self._attempted: set[str] = set()
        self._receipts: dict[str, ActionReceipt] = {}

    def register(self, spec: CapabilitySpec, adapter: CapabilityAdapter) -> None:
        if not isinstance(spec, CapabilitySpec) or not callable(adapter):
            raise TypeError("Trusted spec and callable adapter required")
        if spec.name in self._adapters:
            raise ValueError("Capability already exists; one canonical adapter per name")
        self._adapters[spec.name] = (spec, adapter)

    def registered(self) -> tuple[CapabilitySpec, ...]:
        return tuple(spec for spec, _ in self._adapters.values())

    def receipt(self, request_id: str) -> ActionReceipt | None:
        return self._receipts.get(request_id)

    def execute(self, request: ActionRequest) -> ActionReceipt:
        if not isinstance(request, ActionRequest) or request.owner_id != self.owner_id:
            raise PermissionError("Action owner mismatch")
        if request.request_id in self._attempted:
            raise PermissionError("Action request ID was already attempted")
        registered = self._adapters.get(request.capability)
        if registered is None:
            raise LookupError("No connected adapter for the requested capability")
        spec, adapter = registered
        operation = next((op for op in spec.operations if op.name == request.operation), None)
        if operation is None:
            raise ValueError("Operation not declared by this capability")
        if operation.effect != "local" and (
            self._authorize is None or self._authorize(self.owner_id, request, operation) is not True
        ):
            raise PermissionError("Independent authorization required for this exact external action")
        self._attempted.add(request.request_id)
        result = adapter(request)
        if not isinstance(result, AdapterResult):
            raise TypeError("Trusted adapter returned an invalid result; do not retry automatically")
        receipt = ActionReceipt(
            request_id=request.request_id, owner_id=self.owner_id,
            capability=request.capability, operation=request.operation,
            effect=operation.effect, result=result,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._receipts[request.request_id] = receipt
        return receipt
