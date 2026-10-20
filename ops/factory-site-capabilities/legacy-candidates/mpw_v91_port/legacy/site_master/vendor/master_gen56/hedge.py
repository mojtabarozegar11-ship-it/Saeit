from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dataclasses import dataclass
from time import perf_counter

@dataclass(frozen=True)
class HedgeResult:
    value: object; winner: str; elapsed_ms: float; attempts: int

class HedgedExecutor:
    """Gen51: optional first-success hedging for independent idempotent candidates."""
    def run(self,candidates,timeout_ms=None):
        if not candidates: raise ValueError('no candidates')
        started=perf_counter(); errors=[]
        with ThreadPoolExecutor(max_workers=len(candidates)) as ex:
            futures={ex.submit(fn):name for name,fn in candidates.items()}; pending=set(futures)
            while pending:
                done,pending=wait(pending,timeout=None if timeout_ms is None else max(0,float(timeout_ms)/1000),return_when=FIRST_COMPLETED)
                if not done: raise TimeoutError('hedged execution timeout')
                for fut in sorted(done,key=lambda f:futures[f]):
                    try:
                        value=fut.result(); [x.cancel() for x in pending]
                        return HedgeResult(value,futures[fut],(perf_counter()-started)*1000,len(futures))
                    except Exception as e: errors.append(e)
        raise RuntimeError('all hedged candidates failed') from (errors[-1] if errors else None)
