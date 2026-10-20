from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any, Callable
from master_gen20.dag import DependencyGraphExecutor, NodeResult

class CheckpointStore:
    """Gen23: atomic, checksummed JSON checkpoints for restart-safe DAG execution."""
    def __init__(self, path: str | Path): self.path=Path(path)
    @staticmethod
    def _digest(payload: dict) -> str: return sha256(dumps(payload,sort_keys=True,separators=(",",":"),default=repr).encode()).hexdigest()
    def save(self, values: dict[str, Any]) -> None:
        payload={"values":values}; envelope={"payload":payload,"sha256":self._digest(payload)}; self.path.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile("w",encoding="utf-8",dir=self.path.parent,delete=False) as f:
            f.write(dumps(envelope,sort_keys=True,ensure_ascii=False,default=repr)); tmp=Path(f.name)
        tmp.replace(self.path)
    def load(self) -> dict[str, Any]:
        if not self.path.exists(): return {}
        envelope=loads(self.path.read_text(encoding="utf-8")); payload=envelope.get("payload",{})
        if envelope.get("sha256") != self._digest(payload): raise ValueError("checkpoint integrity verification failed")
        values=payload.get("values",{})
        if not isinstance(values,dict): raise ValueError("invalid checkpoint values")
        return values

@dataclass(frozen=True)
class ResumableGraphRun:
    ok: bool; results: dict[str,NodeResult]; order: tuple[tuple[str,...],...]; resumed: tuple[str,...]; latency_ms: float

class ResumableDAGExecutor:
    """Gen23: resumes successful nodes from an integrity-checked checkpoint; failed branches remain fail-closed."""
    def __init__(self, store: CheckpointStore, max_workers: int = 4): self.store=store; self.max_workers=max(1,int(max_workers))
    def run(self,nodes:dict[str,Callable[[dict[str,Any]],Any]],dependencies:dict[str,tuple[str,...]|list[str]]|None=None):
        dependencies=dependencies or {}; layers=DependencyGraphExecutor._layers(nodes,dependencies); start=perf_counter(); cached=self.store.load(); results={}; resumed=[]
        for name in nodes:
            if name in cached: results[name]=NodeResult(True,cached[name]); resumed.append(name)
        for layer in layers:
            for name in layer:
                if name in results: continue
                bad=[d for d in dependencies.get(name,()) if d not in results or not results[d].ok]
                if bad: results[name]=NodeResult(False,error="blocked_by:"+",".join(sorted(bad))); continue
                t=perf_counter()
                try:
                    ctx={d:results[d].value for d in dependencies.get(name,())}; value=nodes[name](ctx); results[name]=NodeResult(True,value,latency_ms=(perf_counter()-t)*1000)
                    cached[name]=value; self.store.save(cached)
                except Exception as exc: results[name]=NodeResult(False,error=str(exc)[:500],latency_ms=(perf_counter()-t)*1000)
        return ResumableGraphRun(all(r.ok for r in results.values()),results,layers,tuple(sorted(resumed)),(perf_counter()-start)*1000)
