from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Any,Callable

@dataclass(frozen=True)
class NodeResult:
    ok: bool; value: Any=None; error: str|None=None; latency_ms: float=0.0
@dataclass(frozen=True)
class GraphRun:
    ok: bool; results: dict[str,NodeResult]; order: tuple[tuple[str,...],...]; latency_ms: float

class DependencyGraphExecutor:
    """Gen19: bounded parallel execution of an explicit DAG. Failed dependencies block descendants (fail-closed)."""
    def __init__(self,max_workers=4): self.max_workers=max(1,int(max_workers))
    @staticmethod
    def _layers(nodes,deps):
        names=set(nodes); dep={n:set(deps.get(n,())) for n in names}
        unknown={d for ds in dep.values() for d in ds if d not in names}
        if unknown: raise ValueError(f"unknown dependencies: {sorted(unknown)}")
        layers=[]; done=set()
        while len(done)<len(names):
            ready=tuple(sorted(n for n in names-done if dep[n]<=done))
            if not ready: raise ValueError("dependency cycle detected")
            layers.append(ready); done.update(ready)
        return tuple(layers)
    def run(self,nodes:dict[str,Callable[[dict[str,Any]],Any]],dependencies:dict[str,tuple[str,...]|list[str]]|None=None):
        dependencies=dependencies or {}; layers=self._layers(nodes,dependencies); results={}; start=perf_counter()
        for layer in layers:
            runnable=[]
            for name in layer:
                bad=[d for d in dependencies.get(name,()) if not results[d].ok]
                if bad: results[name]=NodeResult(False,error="blocked_by:"+",".join(sorted(bad)))
                else:runnable.append(name)
            def invoke(name):
                t=perf_counter()
                try:
                    ctx={d:results[d].value for d in dependencies.get(name,())}; return name,NodeResult(True,nodes[name](ctx),latency_ms=(perf_counter()-t)*1000)
                except Exception as exc:return name,NodeResult(False,error=str(exc)[:500],latency_ms=(perf_counter()-t)*1000)
            with ThreadPoolExecutor(max_workers=min(self.max_workers,max(1,len(runnable)))) as pool:
                for name,res in pool.map(invoke,runnable): results[name]=res
        return GraphRun(all(r.ok for r in results.values()),results,layers,(perf_counter()-start)*1000)
