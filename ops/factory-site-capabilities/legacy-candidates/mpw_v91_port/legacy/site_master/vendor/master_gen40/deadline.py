from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class DeadlinePlan:
    selected: tuple[str,...]; predicted_ms: float; within_deadline: bool

class DeadlinePlanner:
    """Gen37: deterministic latency-budget planning using observed/predicted milliseconds."""
    def plan(self,names,latency_ms:dict[str,float],deadline_ms:float,min_candidates=1,max_candidates=None):
        ranked=sorted(names,key=lambda n:(max(0.0,float(latency_ms.get(n,0.0))),n)); cap=len(ranked) if max_candidates is None else int(max_candidates)
        chosen=[]; elapsed=0.0
        for n in ranked:
            v=max(0.0,float(latency_ms.get(n,0.0)))
            if len(chosen)<cap and elapsed+v<=float(deadline_ms): chosen.append(n); elapsed+=v
        ok=len(chosen)>=int(min_candidates)
        return DeadlinePlan(tuple(chosen),elapsed,ok)
