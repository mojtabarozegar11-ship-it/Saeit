from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RiskDecision:
    selected: tuple[str,...]; scores: tuple[tuple[str,float],...]

class RiskAwareSelector:
    """Gen49: ranks candidates by learned quality while penalizing failure, latency and cost risk."""
    def select(self,names,quality=None,failure_rate=None,latency_ms=None,costs=None,limit=None):
        names=tuple(names); quality=quality or {}; failure_rate=failure_rate or {}; latency_ms=latency_ms or {}; costs=costs or {}
        max_l=max([max(0.0,float(latency_ms.get(n,0))) for n in names] or [1.0]) or 1.0
        max_c=max([max(0.0,float(costs.get(n,0))) for n in names] or [1.0]) or 1.0
        rows=[]
        for n in names:
            q=max(0.0,min(1.0,float(quality.get(n,.5)))); f=max(0.0,min(1.0,float(failure_rate.get(n,0))))
            l=max(0.0,float(latency_ms.get(n,0)))/max_l; c=max(0.0,float(costs.get(n,0)))/max_c
            rows.append((n,.70*q-.15*f-.10*l-.05*c))
        rows.sort(key=lambda x:(-x[1],x[0])); k=len(rows) if limit is None else max(0,min(len(rows),int(limit)))
        return RiskDecision(tuple(n for n,_ in rows[:k]),tuple(rows))
