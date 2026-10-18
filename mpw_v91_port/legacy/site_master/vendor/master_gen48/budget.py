from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations

@dataclass(frozen=True)
class BudgetDecision:
    selected: tuple[str,...]; total_cost: float; total_latency_ms: float; feasible: bool

class MultiConstraintBudgeter:
    """Gen41: exact deterministic portfolio selection under simultaneous cost/latency constraints."""
    def select(self,names,scores,costs=None,latencies_ms=None,max_cost=float('inf'),max_latency_ms=float('inf'),min_candidates=1,max_candidates=None):
        names=tuple(names); costs=costs or {}; latencies_ms=latencies_ms or {}; cap=len(names) if max_candidates is None else min(len(names),max(0,int(max_candidates)))
        floor=max(0,int(min_candidates)); feasible=[]
        for size in range(floor,cap+1):
            for combo in combinations(sorted(names),size):
                cost=sum(max(0.0,float(costs.get(n,0.0))) for n in combo); lat=sum(max(0.0,float(latencies_ms.get(n,0.0))) for n in combo)
                if cost<=float(max_cost) and lat<=float(max_latency_ms):
                    score=sum(float(scores.get(n,0.0)) for n in combo); feasible.append((score,-cost,-lat,combo,cost,lat))
        if not feasible: return BudgetDecision((),0.0,0.0,False)
        _,_,_,combo,cost,lat=max(feasible,key=lambda x:(x[0],len(x[3]),x[1],x[2],tuple(reversed(x[3]))))
        return BudgetDecision(tuple(combo),cost,lat,True)
