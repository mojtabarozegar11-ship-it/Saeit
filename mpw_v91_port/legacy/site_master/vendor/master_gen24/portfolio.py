from __future__ import annotations
from dataclasses import dataclass
from math import log, sqrt
from typing import Iterable

@dataclass(frozen=True)
class CandidateRecord:
    name: str
    trials: int = 0
    successes: int = 0
    mean_quality: float = 0.0
    mean_cost: float = 0.0
    mean_latency_ms: float = 0.0

@dataclass(frozen=True)
class PortfolioDecision:
    name: str
    score: float
    exploration_bonus: float
    utility: float

class AdaptivePortfolio:
    """Gen22: deterministic UCB-style exploration/exploitation with quality, cost and latency utility."""
    def __init__(self, exploration: float = 0.35, cost_weight: float = 0.08, latency_weight: float = 0.04):
        self.exploration=max(0.0,float(exploration)); self.cost_weight=max(0.0,float(cost_weight)); self.latency_weight=max(0.0,float(latency_weight))
        self._records: dict[str, CandidateRecord] = {}

    def record(self, name: str, success: bool, quality: float, cost: float = 0.0, latency_ms: float = 0.0) -> CandidateRecord:
        old=self._records.get(name,CandidateRecord(name)); n=old.trials+1
        avg=lambda prior,new: prior+(float(new)-prior)/n
        row=CandidateRecord(name,n,old.successes+int(bool(success)),avg(old.mean_quality,quality),avg(old.mean_cost,cost),avg(old.mean_latency_ms,latency_ms))
        self._records[name]=row; return row

    def decision(self, names: Iterable[str]) -> PortfolioDecision:
        names=tuple(sorted(set(names)))
        if not names: raise ValueError("at least one candidate is required")
        total=max(1,sum(self._records.get(n,CandidateRecord(n)).trials for n in names))
        scored=[]
        for name in names:
            r=self._records.get(name,CandidateRecord(name))
            if r.trials == 0: bonus=float("inf"); utility=0.5
            else:
                reliability=r.successes/r.trials
                utility=.55*r.mean_quality+.45*reliability-self.cost_weight*r.mean_cost-self.latency_weight*(r.mean_latency_ms/1000.0)
                bonus=self.exploration*sqrt(log(total+1)/r.trials)
            scored.append(PortfolioDecision(name,utility+bonus,bonus,utility))
        return max(scored,key=lambda x:(x.score,x.utility,x.name))

    def snapshot(self) -> tuple[CandidateRecord, ...]:
        return tuple(self._records[n] for n in sorted(self._records))
