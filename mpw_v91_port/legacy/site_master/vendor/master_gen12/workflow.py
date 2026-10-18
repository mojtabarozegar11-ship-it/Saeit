from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Any

@dataclass(frozen=True)
class WorkflowNode:
    name: str
    fn: Callable[[dict[str, Any]], Any]
    depends_on: tuple[str,...]=()

@dataclass(frozen=True)
class WorkflowResult:
    ok: bool
    values: dict[str,Any]
    errors: dict[str,str]
    latency_ms: float
    execution_order: tuple[str,...]

class DAGExecutor:
    """Executes independent DAG nodes concurrently while preserving dependency correctness."""
    def __init__(self,max_workers=4): self.max_workers=max(1,int(max_workers))
    @staticmethod
    def _validate(nodes):
        names=[n.name for n in nodes]
        if len(names)!=len(set(names)): raise ValueError("duplicate workflow node")
        known=set(names)
        for n in nodes:
            missing=set(n.depends_on)-known
            if missing: raise ValueError(f"unknown dependencies for {n.name}: {sorted(missing)}")
        visiting=set(); done=set(); by={n.name:n for n in nodes}
        def visit(name):
            if name in visiting: raise ValueError("workflow contains a cycle")
            if name in done: return
            visiting.add(name)
            for dep in by[name].depends_on: visit(dep)
            visiting.remove(name); done.add(name)
        for name in names: visit(name)

    def run(self,nodes):
        nodes=tuple(nodes); self._validate(nodes); by={n.name:n for n in nodes}; pending=set(by)
        values={}; errors={}; order=[]; running={}; start=perf_counter()
        def call(node): return node.fn({d:values[d] for d in node.depends_on})
        with ThreadPoolExecutor(max_workers=min(self.max_workers,max(1,len(nodes)))) as pool:
            while pending or running:
                blocked=[n for n in pending if any(d in errors for d in by[n].depends_on)]
                for n in blocked: errors[n]="dependency_failed"; pending.remove(n); order.append(n)
                ready=sorted(n for n in pending if all(d in values for d in by[n].depends_on))
                while ready and len(running)<self.max_workers:
                    name=ready.pop(0); pending.remove(name); running[pool.submit(call,by[name])]=name
                if not running:
                    if pending: raise RuntimeError("workflow stalled")
                    break
                finished,_=wait(tuple(running),return_when=FIRST_COMPLETED)
                for future in sorted(finished,key=lambda f:running[f]):
                    name=running.pop(future); order.append(name)
                    try: values[name]=future.result()
                    except Exception as exc: errors[name]=str(exc)[:500]
        return WorkflowResult(not errors,values,errors,(perf_counter()-start)*1000,tuple(order))
