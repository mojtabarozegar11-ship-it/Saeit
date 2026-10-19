from __future__ import annotations
from dataclasses import dataclass
from random import Random
from statistics import fmean
from master_gen12.proof import MetricSample, FortyPercentProofGate

@dataclass(frozen=True)
class RobustImprovementProof:
    passed: bool
    point_estimate: float
    lower_confidence_bound: float
    confidence: float
    samples: int
    required_improvement: float
    bootstrap_rounds: int

class RobustFortyPercentProofGate:
    """Gen16: requires both Gen12's measured >=40% point estimate and a bootstrap lower bound >=40%."""
    def __init__(self, required_improvement=.40, confidence=.95, bootstrap_rounds=2000, min_samples=8,
                 quality_weight=.70, latency_weight=.20, cost_weight=.10, seed=16):
        self.required=float(required_improvement); self.confidence=max(.50,min(.999,float(confidence)))
        self.rounds=max(200,int(bootstrap_rounds)); self.min_samples=max(2,int(min_samples)); self.seed=int(seed)
        self.base=FortyPercentProofGate(self.required,quality_weight,latency_weight,cost_weight)

    def compare(self, baseline, candidate):
        baseline=tuple(baseline); candidate=tuple(candidate)
        if len(baseline)!=len(candidate): raise ValueError("baseline and candidate sample counts must match")
        if len(baseline)<self.min_samples: raise ValueError(f"at least {self.min_samples} paired samples are required")
        point=self.base.compare(baseline,candidate)
        rng=Random(self.seed); n=len(baseline); estimates=[]
        for _ in range(self.rounds):
            idx=[rng.randrange(n) for _ in range(n)]
            b=[baseline[i] for i in idx]; c=[candidate[i] for i in idx]
            estimates.append(self.base.compare(b,c).improvement)
        estimates.sort(); alpha=1.0-self.confidence; pos=max(0,min(len(estimates)-1,int(alpha*len(estimates))))
        lower=estimates[pos]
        return RobustImprovementProof(bool(point.passed and lower>=self.required),point.improvement,lower,self.confidence,n,self.required,self.rounds)
