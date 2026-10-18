from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from master_gen48 import Generation48Controller
from .risk import RiskAwareSelector
from .circuit import CircuitBreaker
from .hedge import HedgedExecutor
from .cache import AdaptiveResultCache
from .drift import DriftDetector
from .learning import OutcomeLearner
from .slo import SLOGuard

@dataclass(frozen=True)
class Generation56Run:
    base:Any; selected:tuple[str,...]; cache_hit:bool; slo_ok:bool
    @property
    def ok(self): return bool(self.base.ok)
    @property
    def value(self): return self.base.value

class Generation56Controller:
    """Gen56 opt-in facade: Gen48 compatibility + risk learning, circuit isolation, cache and SLO guard."""
    def __init__(self,**gen48_kwargs):
        self.base=Generation48Controller(**gen48_kwargs); self.risk=RiskAwareSelector(); self.circuit=CircuitBreaker(); self.hedge=HedgedExecutor(); self.cache=AdaptiveResultCache(); self.drift=DriftDetector(); self.learning=OutcomeLearner(); self.slo=SLOGuard()
    def run(self,candidates:dict[str,Callable[[],Any]],request_id:str,costs=None,latency_ms=None,min_candidates=1,max_candidates=None,cache_safe=False,cache_key=None,max_error_rate=1.0,max_p95_ms=float('inf'),outcome_quality=None,**kwargs):
        if cache_safe and cache_key is not None:
            hit,value=self.cache.get(cache_key)
            if hit: return value
        available=[n for n in candidates if self.circuit.allowed(n) and self.base.health.allowed(n)]
        q={n:self.learning.estimate(n).mean for n in available}
        fr={}
        for n in available:
            t=self.base.telemetry.summary(n); fr[n]=(t.failures/t.count) if t.count else 0.0
        ranked=self.risk.select(available,q,fr,latency_ms,costs,max_candidates or len(available)).selected
        if len(ranked)<int(min_candidates): raise ValueError('insufficient healthy candidates')
        subset={n:candidates[n] for n in ranked}
        wrapped={}
        for n,fn in subset.items():
            def make(name,f):
                def call():
                    started=perf_counter(); ok=False
                    try: v=f(); ok=True; return v
                    finally:
                        self.circuit.observe(name,ok); self.drift.observe((perf_counter()-started)*1000)
                return call
            wrapped[n]=make(n,fn)
        base=self.base.run(wrapped,str(request_id),costs=costs,latency_ms=latency_ms,min_candidates=min_candidates,max_candidates=max_candidates,**kwargs)
        oq=outcome_quality or {}
        for n in base.selected: self.learning.observe(n,oq.get(n,1.0 if base.ok else 0.0))
        telemetry={n:{'count':s.count,'failures':s.failures,'p95_ms':s.p95_ms} for n in base.selected for s in [self.base.telemetry.summary(n)]}
        decision=self.slo.check(telemetry,max_error_rate,max_p95_ms)
        if not decision.allowed: raise RuntimeError('SLO violation: '+';'.join(decision.reasons))
        result=Generation56Run(base,tuple(base.selected),False,True)
        if cache_safe and cache_key is not None: self.cache.put(cache_key,result)
        return result
