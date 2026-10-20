from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Callable
from master_gen16.telemetry import TamperEvidentTrace
from .semantic_quorum import SemanticQuorumExecutor

@dataclass(frozen=True)
class Generation20Run:
    ok: bool; value: Any; agreement: float; trace_valid: bool; accepted: int

class Generation20Controller:
    """Opt-in Gen20 facade: Gen13 tamper evidence + Gen17 semantic quorum; no legacy mutation."""
    def __init__(self,min_agreement=.60,trace=None,normalizer=None):
        self.trace=trace or TamperEvidentTrace(); self.quorum=SemanticQuorumExecutor(min_agreement=min_agreement,normalizer=normalizer)
    def run(self,candidates:dict[str,Callable[[],Any]],validator=None):
        self.trace.append("gen20_run_started",{"candidates":tuple(candidates)})
        result=self.quorum.run(candidates,validator)
        self.trace.append("gen20_run_finished",{"ok":result.ok,"agreement":result.agreement,"accepted":result.accepted})
        return Generation20Run(result.ok,result.value,result.agreement,self.trace.verify()["valid"],result.accepted)
