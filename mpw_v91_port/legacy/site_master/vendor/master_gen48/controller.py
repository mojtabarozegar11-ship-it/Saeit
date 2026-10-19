from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from master_gen40 import Generation40Controller
from .budget import MultiConstraintBudgeter
from .consensus import WeightedConsensus
from .health import CapabilityHealth
from .policy import ExecutionPolicy
from .telemetry import RuntimeTelemetry
from .checkpoint import CheckpointCodec
from .shadow import ShadowEvaluator

@dataclass(frozen=True)
class Generation48Run:
    base: Any; selected: tuple[str,...]; policy_ok: bool; telemetry: dict
    @property
    def ok(self): return bool(self.base.ok)
    @property
    def value(self): return self.base.value

class Generation48Controller:
    """Gen48 additive facade over unchanged Gen40 with budget, health, policy and telemetry controls."""
    def __init__(self,denied_tags=(),**gen40_kwargs):
        self.base=Generation40Controller(**gen40_kwargs); self.budget=MultiConstraintBudgeter(); self.consensus=WeightedConsensus(); self.health=CapabilityHealth(); self.policy=ExecutionPolicy(denied_tags); self.telemetry=RuntimeTelemetry(); self.checkpoints=CheckpointCodec(); self.shadow=ShadowEvaluator()
    def run(self,candidates:dict[str,Callable[[],Any]],request_id:str,costs=None,latency_ms=None,max_cost=float('inf'),max_latency_ms=float('inf'),scores=None,tags=None,min_candidates=1,max_candidates=None,**kwargs):
        available=[n for n in candidates if self.health.allowed(n)]; scores=scores or {n:self.base.uncertainty.conservative_score(n) for n in available}
        plan=self.budget.select(available,scores,costs,latency_ms,max_cost,max_latency_ms,min_candidates,max_candidates)
        if not plan.feasible: raise ValueError('resource budget cannot satisfy minimum candidates')
        decision=self.policy.check(plan.selected,tags,min_candidates)
        if not decision.allowed: raise PermissionError(';'.join(decision.reasons))
        wrapped={}
        for name in plan.selected:
            fn=candidates[name]
            def make(n,f):
                def call():
                    started=perf_counter(); ok=False
                    try: value=f(); ok=True; return value
                    finally:
                        elapsed=(perf_counter()-started)*1000; self.telemetry.observe(n,elapsed,ok); self.health.observe(n,ok)
                return call
            wrapped[name]=make(name,fn)
        base=self.base.run(wrapped,request_id,min_candidates=min_candidates,max_candidates=max_candidates,latency_ms=latency_ms,**kwargs)
        return Generation48Run(base,tuple(plan.selected),True,self.telemetry.snapshot())
    def checkpoint(self):
        snap=self.base.snapshot(); return self.checkpoints.encode(snap.version,{'gen40':snap.payload,'health':self.health.snapshot(),'telemetry':self.telemetry.snapshot()})
