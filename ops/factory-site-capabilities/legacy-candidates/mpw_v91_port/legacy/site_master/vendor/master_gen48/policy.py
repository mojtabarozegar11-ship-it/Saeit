from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool; reasons: tuple[str,...]

class ExecutionPolicy:
    """Gen44: fail-closed execution policy for allow/deny tags and hard candidate floors."""
    def __init__(self,denied_tags=()): self.denied=frozenset(str(x) for x in denied_tags)
    def check(self,selected,tags=None,min_candidates=1):
        tags=tags or {}; reasons=[]
        if len(tuple(selected))<int(min_candidates): reasons.append('candidate_floor')
        for n in selected:
            hit=sorted(self.denied.intersection(map(str,tags.get(n,()))))
            if hit: reasons.append(f'{n}:denied:'+','.join(hit))
        return PolicyDecision(not reasons,tuple(reasons))
