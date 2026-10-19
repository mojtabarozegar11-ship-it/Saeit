from __future__ import annotations
from dataclasses import dataclass
from statistics import fmean
from typing import Iterable

@dataclass(frozen=True)
class MetricSample:
    quality: float
    latency_ms: float
    cost: float=0.0

@dataclass(frozen=True)
class ImprovementProof:
    passed: bool
    improvement: float
    baseline_utility: float
    candidate_utility: float
    quality_gain: float
    latency_gain: float
    cost_gain: float
    samples: int
    required_improvement: float

class FortyPercentProofGate:
    """Requires measured composite utility improvement; it never infers or fabricates a 40% gain."""
    def __init__(self, required_improvement=.40, quality_weight=.70, latency_weight=.20, cost_weight=.10):
        self.required=float(required_improvement)
        weights=(float(quality_weight),float(latency_weight),float(cost_weight)); total=sum(weights)
        if total<=0: raise ValueError("weights must sum to > 0")
        self.weights=tuple(w/total for w in weights)

    @staticmethod
    def _avg(rows: Iterable[MetricSample]):
        rows=tuple(rows)
        if not rows: raise ValueError("at least one metric sample is required")
        return (fmean(r.quality for r in rows),fmean(r.latency_ms for r in rows),fmean(r.cost for r in rows),len(rows))

    def compare(self, baseline, candidate):
        bq,bl,bc,bn=self._avg(baseline); cq,cl,cc,cn=self._avg(candidate)
        if bn!=cn: raise ValueError("baseline and candidate sample counts must match")
        q_gain=(cq-bq)/bq if bq>0 else (1.0 if cq>0 else 0.0)
        l_gain=(bl-cl)/bl if bl>0 else 0.0
        c_gain=(bc-cc)/bc if bc>0 else 0.0
        qw,lw,cw=self.weights
        # Utility is relative to the measured baseline; positive means objectively better under declared weights.
        improvement=qw*q_gain+lw*l_gain+cw*c_gain
        baseline_utility=1.0
        candidate_utility=1.0+improvement
        return ImprovementProof(improvement>=self.required,improvement,baseline_utility,candidate_utility,q_gain,l_gain,c_gain,bn,self.required)
