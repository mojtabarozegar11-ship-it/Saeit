from __future__ import annotations
from dataclasses import dataclass
from typing import Hashable, Sequence
from master_gen24 import StratifiedFortyPercentProofGate

@dataclass(frozen=True)
class GenerationUpgradeProof:
    passed: bool
    performance_passed: bool
    compatibility_passed: bool
    required_improvement: float
    details: object

class Generation28ProofGate:
    """Gen28: a release passes only when robust stratified >=40% evidence AND compatibility preservation both pass."""
    def __init__(self,required_improvement=.40,**kwargs):
        self.required=float(required_improvement); self.performance=StratifiedFortyPercentProofGate(required_improvement=self.required,**kwargs)
    def compare(self,baseline:Sequence,candidate:Sequence,strata:Sequence[Hashable],compatibility_ok:bool):
        detail=self.performance.compare(baseline,candidate,strata)
        compat=bool(compatibility_ok)
        return GenerationUpgradeProof(detail.passed and compat,detail.passed,compat,self.required,detail)
