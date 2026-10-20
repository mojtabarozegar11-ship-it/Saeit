from __future__ import annotations
from dataclasses import dataclass
from statistics import median
from master_gen16.proof import RobustFortyPercentProofGate

@dataclass(frozen=True)
class HoldoutImprovementProof:
    passed: bool; median_point_estimate: float; worst_lower_bound: float; folds: int; required_improvement: float; fold_proofs: tuple

class HoldoutFortyPercentProofGate:
    """Gen20: >=40% must survive multiple deterministic holdout folds, not only one pooled sample."""
    def __init__(self,required_improvement=.40,folds=3,confidence=.95,bootstrap_rounds=1200,min_samples_per_fold=4,seed=20):
        self.required=float(required_improvement); self.folds=max(2,int(folds)); self.confidence=float(confidence); self.rounds=max(200,int(bootstrap_rounds)); self.min_per=max(2,int(min_samples_per_fold)); self.seed=int(seed)
    def compare(self,baseline,candidate):
        baseline=tuple(baseline); candidate=tuple(candidate)
        if len(baseline)!=len(candidate): raise ValueError("baseline and candidate sample counts must match")
        if len(baseline)<self.folds*self.min_per: raise ValueError(f"at least {self.folds*self.min_per} paired samples are required")
        proofs=[]
        for fold in range(self.folds):
            b=baseline[fold::self.folds]; c=candidate[fold::self.folds]
            gate=RobustFortyPercentProofGate(self.required,self.confidence,self.rounds,self.min_per,seed=self.seed+fold)
            proofs.append(gate.compare(b,c))
        point=median(p.point_estimate for p in proofs); lower=min(p.lower_confidence_bound for p in proofs)
        return HoldoutImprovementProof(all(p.passed for p in proofs) and point>=self.required and lower>=self.required,point,lower,self.folds,self.required,tuple(proofs))
