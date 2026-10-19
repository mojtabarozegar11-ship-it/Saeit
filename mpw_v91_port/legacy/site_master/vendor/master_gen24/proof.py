from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from typing import Hashable, Sequence
from master_gen16.proof import RobustFortyPercentProofGate

@dataclass(frozen=True)
class StratifiedImprovementProof:
    passed: bool; median_point_estimate: float; worst_lower_bound: float; strata: int; required_improvement: float; stratum_proofs: tuple

class StratifiedFortyPercentProofGate:
    """Gen24: >=40% must hold independently across declared workload strata, preventing aggregate wins from hiding regressions."""
    def __init__(self,required_improvement=.40,confidence=.95,bootstrap_rounds=1200,min_samples_per_stratum=4,seed=24):
        self.required=float(required_improvement); self.confidence=float(confidence); self.rounds=max(200,int(bootstrap_rounds)); self.min_per=max(2,int(min_samples_per_stratum)); self.seed=int(seed)
    def compare(self,baseline:Sequence[float],candidate:Sequence[float],strata:Sequence[Hashable]):
        if not (len(baseline)==len(candidate)==len(strata)): raise ValueError("baseline, candidate and strata counts must match")
        keys=tuple(sorted(set(strata),key=repr))
        if len(keys)<2: raise ValueError("at least two workload strata are required")
        proofs=[]
        for i,key in enumerate(keys):
            idx=[j for j,s in enumerate(strata) if s==key]
            if len(idx)<self.min_per: raise ValueError(f"stratum {key!r} requires at least {self.min_per} samples")
            b=[baseline[j] for j in idx]; c=[candidate[j] for j in idx]
            proof=RobustFortyPercentProofGate(self.required,self.confidence,self.rounds,self.min_per,seed=self.seed+i).compare(b,c)
            proofs.append((key,proof))
        point=median(p.point_estimate for _,p in proofs); lower=min(p.lower_confidence_bound for _,p in proofs)
        return StratifiedImprovementProof(all(p.passed for _,p in proofs) and point>=self.required and lower>=self.required,point,lower,len(keys),self.required,tuple(proofs))
