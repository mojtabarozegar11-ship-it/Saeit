from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .adaptive import AdaptiveCapabilityRegistry

@dataclass(frozen=True)
class RouteDecision:
    selected: tuple[str,...]
    rejected: tuple[str,...]
    estimated_cost: float

class RiskAwareRouter:
    """Gen30: chooses the strongest affordable quorum portfolio, fail-closed on impossible constraints."""
    def __init__(self,registry:AdaptiveCapabilityRegistry): self.registry=registry
    def select(self,names:Iterable[str],costs:dict[str,float]|None=None,max_cost=float('inf'),min_candidates=1,max_candidates:int|None=None):
        costs=costs or {}; ranked=self.registry.rank(names); limit=max_candidates or len(ranked)
        chosen=[]; spent=0.0
        for name in ranked:
            c=max(0.0,float(costs.get(name,0.0)))
            if len(chosen)<limit and spent+c<=max_cost: chosen.append(name); spent+=c
        if len(chosen)<int(min_candidates): raise ValueError('insufficient affordable candidates')
        return RouteDecision(tuple(chosen),tuple(n for n in ranked if n not in chosen),spent)
