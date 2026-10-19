from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
import json


def canonical_json(value: Any) -> str:
    """Stable structural representation. Dict key order and set order do not create false disagreement."""
    def clean(v):
        if isinstance(v, dict): return {str(k):clean(v[k]) for k in sorted(v,key=str)}
        if isinstance(v, (set,frozenset)): return sorted((clean(x) for x in v),key=lambda x:json.dumps(x,sort_keys=True,default=repr))
        if isinstance(v, (list,tuple)): return [clean(x) for x in v]
        return v
    return json.dumps(clean(value),sort_keys=True,separators=(",",":"),ensure_ascii=False,default=repr)

@dataclass(frozen=True)
class SemanticQuorumResult:
    ok: bool; value: Any; agreement: float; accepted: int; attempted: int; errors: tuple[str,...]; latency_ms: float; winning_key: str|None

class SemanticQuorumExecutor:
    """Gen17: validated parallel quorum with caller-controlled semantic normalization."""
    def __init__(self,min_agreement=.60,max_workers=4,normalizer:Callable[[Any],Any]|None=None):
        self.min_agreement=max(0.0,min(1.0,float(min_agreement))); self.max_workers=max(1,int(max_workers)); self.normalizer=normalizer or canonical_json
    def run(self,candidates:dict[str,Callable[[],Any]],validator:Callable[[Any],bool]|None=None):
        if not candidates: raise ValueError("at least one candidate is required")
        start=perf_counter(); accepted=[]; errors=[]
        def call(name,fn):
            try:
                value=fn()
                if validator is not None and not bool(validator(value)): return name,None,"validation_failed"
                return name,value,None
            except Exception as exc: return name,None,str(exc)[:500]
        with ThreadPoolExecutor(max_workers=min(self.max_workers,len(candidates))) as pool:
            futures=[pool.submit(call,n,f) for n,f in candidates.items()]
            for f in as_completed(futures):
                name,value,error=f.result()
                (accepted.append((name,value)) if error is None else errors.append(f"{name}:{error}"))
        if not accepted: return SemanticQuorumResult(False,None,0.0,0,len(candidates),tuple(sorted(errors)),(perf_counter()-start)*1000,None)
        groups={}
        for name,value in accepted:
            key=str(self.normalizer(value)); groups.setdefault(key,[]).append((name,value))
        key,rows=max(groups.items(),key=lambda kv:(len(kv[1]),kv[0]))
        agreement=len(rows)/len(accepted); value=sorted(rows,key=lambda x:list(candidates).index(x[0]))[0][1]
        return SemanticQuorumResult(agreement>=self.min_agreement,value,agreement,len(accepted),len(candidates),tuple(sorted(errors)),(perf_counter()-start)*1000,key)
