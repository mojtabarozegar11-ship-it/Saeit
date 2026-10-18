from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

@dataclass(frozen=True)
class ConsensusDecision:
    value: Any; weight: float; total_weight: float; confidence: float; supporters: tuple[str,...]

class WeightedConsensus:
    """Gen42: reliability-weighted consensus with pluggable normalization."""
    def decide(self,values:dict[str,Any],weights:dict[str,float]|None=None,normalizer:Callable[[Any],Any]|None=None):
        if not values: raise ValueError('no values')
        weights=weights or {}; normalizer=normalizer or (lambda x:x); groups=defaultdict(lambda:[0.0,[]])
        for name,value in values.items():
            key=normalizer(value); w=max(0.0,float(weights.get(name,1.0))); groups[key][0]+=w; groups[key][1].append(name)
        key,(win,supporters)=min(groups.items(),key=lambda kv:(-kv[1][0],repr(kv[0])))
        total=sum(max(0.0,float(weights.get(n,1.0))) for n in values)
        return ConsensusDecision(key,win,total,win/total if total else 0.0,tuple(sorted(supporters)))
