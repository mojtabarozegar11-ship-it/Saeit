from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Mapping

@dataclass(frozen=True)
class ContractResult:
    ok: bool
    value: Any = None
    violations: tuple[str, ...] = ()

class ContractGuard:
    """Gen21: explicit pre/post/invariant contracts. Violations fail closed without mutating legacy code."""
    def __init__(self, pre: Callable[[Mapping[str, Any]], bool] | None = None,
                 post: Callable[[Any], bool] | None = None,
                 invariants: tuple[Callable[[Mapping[str, Any], Any], bool], ...] = ()):
        self.pre = pre
        self.post = post
        self.invariants = tuple(invariants)

    def run(self, fn: Callable[..., Any], /, **kwargs: Any) -> ContractResult:
        violations: list[str] = []
        try:
            if self.pre is not None and not bool(self.pre(kwargs)):
                return ContractResult(False, violations=("precondition_failed",))
            value = fn(**kwargs)
            if self.post is not None and not bool(self.post(value)):
                violations.append("postcondition_failed")
            for i, invariant in enumerate(self.invariants):
                if not bool(invariant(kwargs, value)):
                    violations.append(f"invariant_{i}_failed")
            return ContractResult(not violations, value if not violations else None, tuple(violations))
        except Exception as exc:
            return ContractResult(False, violations=(f"exception:{type(exc).__name__}:{str(exc)[:300]}",))
