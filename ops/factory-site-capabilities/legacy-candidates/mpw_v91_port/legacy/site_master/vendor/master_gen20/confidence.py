from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist
from typing import Iterable
from master_gen16.contextual import ContextualPerformanceMemory

@dataclass(frozen=True)
class ConfidenceScore:
    name: str; score: float; success_lower_bound: float; trials: int

class ConfidenceAwareRouter:
    """Gen18: routes on conservative Wilson reliability, quality and resource penalties; sparse evidence cannot masquerade as certainty."""
    def __init__(self,memory=None,confidence=.95,quality_weight=.35,reliability_weight=.65):
        self.memory=memory or ContextualPerformanceMemory(); self.confidence=max(.50,min(.999,float(confidence)))
        total=float(quality_weight)+float(reliability_weight)
        if total<=0: raise ValueError("weights must sum to > 0")
        self.qw=float(quality_weight)/total; self.rw=float(reliability_weight)/total
    def _lower(self,successes,trials):
        if trials<=0:return 0.0
        z=NormalDist().inv_cdf(.5+self.confidence/2); p=successes/trials; den=1+z*z/trials
        return max(0.0,(p+z*z/(2*trials)-z*sqrt((p*(1-p)+z*z/(4*trials))/trials))/den)
    def score(self,context,capability):
        s=self.memory.stats(context,capability.name); lower=self._lower(s.successes,s.trials)
        quality=s.quality if s.trials else max(0.0,min(1.0,float(capability.quality)))
        evidence=min(1.0,s.trials/8.0); reliability=evidence*lower+(1-evidence)*.50
        latency=min(max(float(capability.latency_ms),0.0)/10000,.15); cost=min(max(float(capability.cost),0.0)/100,.15)
        return ConfidenceScore(capability.name,self.rw*reliability+self.qw*quality-latency-cost,lower,s.trials)
    def rank(self,context:str,required:Iterable[str],capabilities):
        req=frozenset(required); eligible=[c for c in capabilities if c.healthy and req.issubset(c.skills)]
        return sorted(eligible,key=lambda c:(self.score(context,c).score,c.quality,-c.latency_ms,c.name),reverse=True)
    def choose(self,context,required,capabilities):
        rows=self.rank(context,required,capabilities); return rows[0] if rows else None
