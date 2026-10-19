from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from master_gen28 import Generation28Controller
from .adaptive import AdaptiveCapabilityRegistry
from .router import RiskAwareRouter, RouteDecision
from .resilience import DeterministicCircuitBreaker

@dataclass(frozen=True)
class Generation32Run:
    ok: bool
    value: Any
    agreement: float
    trace_valid: bool
    accepted: int
    contract_ok: bool
    recovered: bool
    route: RouteDecision
    attempted: tuple[str,...]

class Generation32Controller:
    """Gen32 additive facade: adaptive routing + circuit isolation layered over unchanged Gen28 semantics."""
    def __init__(self,min_agreement=.60,trace=None,normalizer=None,output_contract=None,recovery_attempts=2,alpha=.25,failure_threshold=3,cooldown_ticks=5):
        self.base=Generation28Controller(min_agreement=min_agreement,trace=trace,normalizer=normalizer,output_contract=output_contract,recovery_attempts=recovery_attempts)
        self.registry=AdaptiveCapabilityRegistry(alpha); self.router=RiskAwareRouter(self.registry); self.breaker=DeterministicCircuitBreaker(failure_threshold,cooldown_ticks)
    def run(self,candidates:dict[str,Callable[[],Any]],validator=None,repair=None,fallbacks=None,costs=None,max_cost=float('inf'),min_candidates=1,max_candidates=None,tick=0,quality_fn:Callable[[Any],float]|None=None):
        available=[n for n in candidates if self.breaker.allow(n,tick)]
        route=self.router.select(available,costs,max_cost,min_candidates,max_candidates)
        attempted=[]; wrapped={}
        for name in route.selected:
            fn=candidates[name]
            def make(n,f):
                def call():
                    started=perf_counter(); attempted.append(n)
                    try:
                        value=f(); ok=True
                        if validator is not None: ok=bool(validator(value))
                        quality=float(quality_fn(value)) if quality_fn else (1.0 if ok else 0.0)
                        self.registry.observe(n,ok,quality,(perf_counter()-started)*1000,(costs or {}).get(n,0.0)); self.breaker.record(n,ok,tick)
                        if not ok: raise ValueError('candidate validation failed')
                        return value
                    except Exception:
                        self.registry.observe(n,False,0.0,(perf_counter()-started)*1000,(costs or {}).get(n,0.0)); self.breaker.record(n,False,tick); raise
                return call
            wrapped[name]=make(name,fn)
        result=self.base.run(wrapped,validator=None,repair=repair,fallbacks=fallbacks)
        return Generation32Run(result.ok,result.value,result.agreement,result.trace_valid,result.accepted,result.contract_ok,result.recovered,route,tuple(attempted))
