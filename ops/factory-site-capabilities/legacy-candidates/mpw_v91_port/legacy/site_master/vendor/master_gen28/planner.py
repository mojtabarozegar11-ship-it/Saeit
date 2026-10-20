from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Iterable

@dataclass(frozen=True)
class PlanStep:
    name: str
    dependencies: tuple[str,...]=()
    estimated_cost: float=0.0
    estimated_latency_ms: float=0.0
    priority: int=0

@dataclass(frozen=True)
class ExecutionPlan:
    steps: tuple[PlanStep,...]
    total_cost: float
    critical_latency_ms: float

class BudgetAwarePlanner:
    """Gen26: deterministic dependency-aware planning under cost/latency budgets."""
    def build(self,steps:Iterable[PlanStep],max_cost=float("inf"),max_latency_ms=float("inf")):
        rows={s.name:s for s in steps}
        if not rows: return ExecutionPlan((),0.0,0.0)
        for s in rows.values():
            missing=set(s.dependencies)-set(rows)
            if missing: raise ValueError("unknown dependencies:"+",".join(sorted(missing)))
        visiting=set(); done=set(); order=[]; latency={}
        def visit(name):
            if name in visiting: raise ValueError("cycle detected")
            if name in done: return
            visiting.add(name)
            for dep in sorted(rows[name].dependencies): visit(dep)
            visiting.remove(name); done.add(name); order.append(rows[name])
            latency[name]=rows[name].estimated_latency_ms+max((latency[d] for d in rows[name].dependencies),default=0.0)
        for name in sorted(rows,key=lambda n:(-rows[n].priority,n)): visit(name)
        cost=sum(max(0.0,s.estimated_cost) for s in order); critical=max(latency.values(),default=0.0)
        if cost>max_cost: raise ValueError("cost budget exceeded")
        if critical>max_latency_ms: raise ValueError("latency budget exceeded")
        return ExecutionPlan(tuple(order),cost,critical)
