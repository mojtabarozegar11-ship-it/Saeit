from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from master_gen24 import Generation24Controller
from .recovery import SelfHealingExecutor

@dataclass(frozen=True)
class Generation28Run:
    ok: bool
    value: Any
    agreement: float
    trace_valid: bool
    accepted: int
    contract_ok: bool
    recovered: bool

class Generation28Controller:
    """Gen28 additive facade: Gen24-compatible quorum/contracts plus opt-in self-healing execution."""
    def __init__(self,min_agreement=.60,trace=None,normalizer=None,output_contract:Callable[[Any],bool]|None=None,recovery_attempts=2):
        self.base=Generation24Controller(min_agreement=min_agreement,trace=trace,normalizer=normalizer,output_contract=output_contract)
        self.recovery=SelfHealingExecutor(attempts=recovery_attempts)
    def run(self,candidates:dict[str,Callable[[],Any]],validator=None,repair=None,fallbacks:dict[str,Callable[[],Any]]|None=None):
        fallbacks=fallbacks or {}; recovered=False
        wrapped={}
        for name,fn in candidates.items():
            def make(n,f):
                def call():
                    nonlocal recovered
                    result=self.recovery.run(f,repair=repair,fallback=fallbacks.get(n),validator=validator)
                    recovered = recovered or result.used_fallback or result.attempts>1
                    if not result.ok: raise RuntimeError(";".join(result.errors))
                    return result.value
                return call
            wrapped[name]=make(name,fn)
        base=self.base.run(wrapped,validator=None)
        return Generation28Run(base.ok,base.value,base.agreement,base.trace_valid,base.accepted,base.contract_ok,recovered)
