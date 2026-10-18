from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class DiverseSelection:
    selected: tuple[str,...]
    domains: tuple[str,...]
    score: float

class DiversityPortfolio:
    """Gen34: greedy quality/diversity portfolio to reduce correlated failure concentration."""
    def select(self,names:Iterable[str],scores:dict[str,float],domains:dict[str,str]|None=None,limit=3,diversity_bonus=.15):
        domains=domains or {}; remaining=set(names); chosen=[]; total=0.0
        while remaining and len(chosen)<max(0,int(limit)):
            used={domains.get(x,x) for x in chosen}
            def utility(n): return float(scores.get(n,0.0))+(float(diversity_bonus) if domains.get(n,n) not in used else 0.0)
            pick=min(remaining,key=lambda n:(-utility(n),n)); total+=utility(pick); chosen.append(pick); remaining.remove(pick)
        return DiverseSelection(tuple(chosen),tuple(domains.get(n,n) for n in chosen),total)
