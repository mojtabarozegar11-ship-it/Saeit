from __future__ import annotations
from dataclasses import dataclass
from math import log, sqrt
from threading import RLock
from typing import Iterable

@dataclass
class ContextStats:
    trials: int=0; successes: int=0; quality_sum: float=0.0; latency_sum_ms: float=0.0; cost_sum: float=0.0
    @property
    def success_rate(self): return self.successes/self.trials if self.trials else 0.0
    @property
    def quality(self): return self.quality_sum/self.trials if self.trials else 0.0

class ContextualPerformanceMemory:
    """Gen15: learns capability performance per explicit context without altering legacy memory."""
    def __init__(self): self._rows={}; self._lock=RLock()
    def record(self, context, capability, *, success, quality=1.0, latency_ms=0.0, cost=0.0):
        key=(str(context),str(capability))
        with self._lock:
            s=self._rows.setdefault(key,ContextStats()); s.trials+=1; s.successes+=int(bool(success))
            s.quality_sum+=max(0.0,min(1.0,float(quality))); s.latency_sum_ms+=max(0.0,float(latency_ms)); s.cost_sum+=max(0.0,float(cost)); return s
    def stats(self, context, capability):
        with self._lock: return self._rows.get((str(context),str(capability)),ContextStats())

class ContextualRouter:
    """Ranks compatible capabilities using context-specific evidence plus bounded exploration."""
    def __init__(self, memory=None, exploration=.10): self.memory=memory or ContextualPerformanceMemory(); self.exploration=max(0.0,float(exploration))
    def rank(self, context: str, required: Iterable[str], capabilities):
        req=frozenset(required); eligible=[c for c in capabilities if c.healthy and req.issubset(c.skills)]
        total=max(1,sum(self.memory.stats(context,c.name).trials for c in eligible))
        def score(c):
            s=self.memory.stats(context,c.name)
            learned=(.60*s.success_rate+.40*s.quality) if s.trials else max(0.0,min(1.0,float(c.quality)))
            explore=self.exploration*sqrt(log(total+1)/(s.trials+1))
            latency=min(max(float(c.latency_ms),0.0)/10000,.15); cost=min(max(float(c.cost),0.0)/100,.15)
            return learned+explore-latency-cost
        return sorted(eligible,key=lambda c:(score(c),c.quality,-c.latency_ms,c.name),reverse=True)
    def choose(self, context, required, capabilities):
        ranked=self.rank(context,required,capabilities); return ranked[0] if ranked else None
