from __future__ import annotations
from dataclasses import dataclass, asdict
from math import log, sqrt
from typing import Dict, Iterable

@dataclass(frozen=True)
class CapabilityStats:
    calls: int = 0
    successes: int = 0
    quality_ewma: float = 0.5
    latency_ewma_ms: float = 0.0
    cost_ewma: float = 0.0

class AdaptiveCapabilityRegistry:
    """Gen29: online, bounded-memory capability learning without touching legacy agents."""
    def __init__(self, alpha: float = 0.25):
        if not 0 < alpha <= 1: raise ValueError("alpha must be in (0,1]")
        self.alpha=float(alpha); self._stats: Dict[str, CapabilityStats]={}
    def observe(self,name:str,ok:bool,quality:float=1.0,latency_ms:float=0.0,cost:float=0.0):
        old=self._stats.get(name,CapabilityStats())
        a=self.alpha
        q=max(0.0,min(1.0,float(quality)))
        lat=max(0.0,float(latency_ms)); c=max(0.0,float(cost))
        first=old.calls==0
        row=CapabilityStats(old.calls+1,old.successes+int(bool(ok)),q if first else (1-a)*old.quality_ewma+a*q,lat if first else (1-a)*old.latency_ewma_ms+a*lat,c if first else (1-a)*old.cost_ewma+a*c)
        self._stats[name]=row; return row
    def get(self,name:str): return self._stats.get(name,CapabilityStats())
    def score(self,name:str,total_calls:int|None=None,latency_weight=.001,cost_weight=.05,exploration=.12):
        s=self.get(name); n=max(1,s.calls); total=max(n+1,total_calls or sum(x.calls for x in self._stats.values())+1)
        success=s.successes/n if s.calls else .5
        bonus=float(exploration)*sqrt(log(total)/n)
        return .55*s.quality_ewma+.45*success+bonus-float(latency_weight)*s.latency_ewma_ms-float(cost_weight)*s.cost_ewma
    def rank(self,names:Iterable[str]):
        names=tuple(names); total=sum(self.get(n).calls for n in names)+1
        return tuple(sorted(names,key=lambda n:(-self.score(n,total),n)))
    def snapshot(self): return {k:asdict(v) for k,v in sorted(self._stats.items())}
