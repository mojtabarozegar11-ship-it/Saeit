from __future__ import annotations
from dataclasses import dataclass
from time import perf_counter, sleep
from typing import Any, Callable

@dataclass(frozen=True)
class RecoveryResult:
    ok: bool
    value: Any=None
    attempts: int=0
    used_fallback: bool=False
    errors: tuple[str,...]=()
    latency_ms: float=0.0

class SelfHealingExecutor:
    """Gen27: bounded retry + repair hook + fallback; failures remain fail-closed."""
    def __init__(self,attempts=3,backoff_seconds=0.0):
        self.attempts=max(1,int(attempts)); self.backoff=max(0.0,float(backoff_seconds))
    def run(self,primary:Callable[[],Any],repair:Callable[[Exception,int],None]|None=None,fallback:Callable[[],Any]|None=None,validator:Callable[[Any],bool]|None=None):
        start=perf_counter(); errors=[]
        for i in range(1,self.attempts+1):
            try:
                value=primary()
                if validator is not None and not bool(validator(value)): raise ValueError("validation_failed")
                return RecoveryResult(True,value,i,False,tuple(errors),(perf_counter()-start)*1000)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}:{str(exc)[:300]}")
                if repair is not None:
                    try: repair(exc,i)
                    except Exception as repair_exc: errors.append(f"repair:{type(repair_exc).__name__}:{str(repair_exc)[:300]}")
                if self.backoff and i<self.attempts: sleep(self.backoff*i)
        if fallback is not None:
            try:
                value=fallback()
                if validator is not None and not bool(validator(value)): raise ValueError("fallback_validation_failed")
                return RecoveryResult(True,value,self.attempts,True,tuple(errors),(perf_counter()-start)*1000)
            except Exception as exc: errors.append(f"fallback:{type(exc).__name__}:{str(exc)[:300]}")
        return RecoveryResult(False,None,self.attempts,False,tuple(errors),(perf_counter()-start)*1000)
