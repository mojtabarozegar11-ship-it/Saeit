from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from .telemetry import TamperEvidentTrace
from .quorum import ValidatedQuorumExecutor

@dataclass(frozen=True)
class Generation16Run:
    ok: bool; value: Any; agreement: float; trace_valid: bool

class Generation16Controller:
    """Opt-in facade: composes Gen13 trace + Gen14 quorum while leaving all older entry points intact."""
    def __init__(self, min_agreement=.60, trace=None):
        self.trace=trace or TamperEvidentTrace(); self.quorum=ValidatedQuorumExecutor(min_agreement=min_agreement)
    def run(self, candidates: dict[str,Callable[[],Any]], validator=None):
        self.trace.append("run_started",{"candidates":tuple(candidates)})
        result=self.quorum.run(candidates,validator)
        self.trace.append("run_finished",{"ok":result.ok,"agreement":result.agreement,"accepted":result.accepted})
        return Generation16Run(result.ok,result.value,result.agreement,self.trace.verify()["valid"])
