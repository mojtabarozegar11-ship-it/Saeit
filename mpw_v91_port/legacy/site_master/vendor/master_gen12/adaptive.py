from __future__ import annotations
from dataclasses import dataclass
from math import exp

@dataclass(frozen=True)
class CandidateSignal:
    name: str
    quality: float
    latency_ms: float
    cost: float
    confidence: float=1.0

class ParetoSelector:
    """Filters dominated candidates, then scores the frontier with explicit normalized weights."""
    def __init__(self, quality_weight=.65, latency_weight=.20, cost_weight=.15):
        total=quality_weight+latency_weight+cost_weight
        if total<=0: raise ValueError("weights must sum to > 0")
        self.weights=(quality_weight/total,latency_weight/total,cost_weight/total)
    @staticmethod
    def frontier(candidates):
        rows=list(candidates); out=[]
        for a in rows:
            dominated=any((b.quality>=a.quality and b.latency_ms<=a.latency_ms and b.cost<=a.cost) and
                          (b.quality>a.quality or b.latency_ms<a.latency_ms or b.cost<a.cost) for b in rows if b is not a)
            if not dominated: out.append(a)
        return out
    def choose(self,candidates):
        rows=self.frontier(candidates)
        if not rows: return None
        max_l=max((r.latency_ms for r in rows),default=1) or 1; max_c=max((r.cost for r in rows),default=1) or 1
        qw,lw,cw=self.weights
        def score(r):
            return qw*max(0,min(1,r.quality))*max(0,min(1,r.confidence))+lw*(1-r.latency_ms/max_l)+cw*(1-r.cost/max_c)
        return max(rows,key=lambda r:(score(r),r.quality,-r.latency_ms,r.name))

class ConfidenceCalibrator:
    """Simple bounded online calibration using exponentially weighted observed correctness."""
    def __init__(self, alpha=.15, initial=.5): self.alpha=max(0,min(1,float(alpha))); self.value=max(0,min(1,float(initial)))
    def update(self, correct: bool):
        self.value=(1-self.alpha)*self.value+self.alpha*float(bool(correct)); return self.value
