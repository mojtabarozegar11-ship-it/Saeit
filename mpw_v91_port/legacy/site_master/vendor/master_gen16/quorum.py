from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable

@dataclass(frozen=True)
class QuorumResult:
    ok: bool
    value: Any
    agreement: float
    accepted: int
    attempted: int
    errors: tuple[str,...]
    latency_ms: float

class ValidatedQuorumExecutor:
    """Gen14: parallel candidate execution + validation + quorum. Invalid outputs never vote."""
    def __init__(self, min_agreement=.60, max_workers=4):
        self.min_agreement=max(0.0,min(1.0,float(min_agreement))); self.max_workers=max(1,int(max_workers))

    def run(self, candidates: dict[str,Callable[[],Any]], validator: Callable[[Any],bool] | None=None):
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
            for future in as_completed(futures):
                name,value,error=future.result()
                if error is None: accepted.append((name,value))
                else: errors.append(f"{name}:{error}")
        if not accepted: return QuorumResult(False,None,0.0,0,len(candidates),tuple(sorted(errors)),(perf_counter()-start)*1000)
        groups=[]
        for name,value in accepted:
            for i,(v,names) in enumerate(groups):
                if value==v: groups[i]=(v,names+[name]); break
            else: groups.append((value,[name]))
        value,names=max(groups,key=lambda row:(len(row[1]),-min(list(candidates).index(n) for n in row[1])))
        agreement=len(names)/len(accepted)
        return QuorumResult(agreement>=self.min_agreement,value,agreement,len(accepted),len(candidates),tuple(sorted(errors)),(perf_counter()-start)*1000)
