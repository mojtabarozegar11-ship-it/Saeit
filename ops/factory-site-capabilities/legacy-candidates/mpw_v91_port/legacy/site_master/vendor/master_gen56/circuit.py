from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CircuitState:
    failures:int; successes:int; open:bool

class CircuitBreaker:
    """Gen50: deterministic per-capability circuit breaker with explicit recovery probes."""
    def __init__(self,failure_threshold=3,recovery_successes=2): self.threshold=max(1,int(failure_threshold)); self.recovery=max(1,int(recovery_successes)); self._s={}
    def observe(self,name,ok):
        f,s,o=self._s.get(name,(0,0,False))
        if ok:
            s+=1; f=0
            if o and s>=self.recovery: o=False; s=0
        else:
            f+=1; s=0
            if f>=self.threshold: o=True
        self._s[name]=(f,s,o); return self.state(name)
    def state(self,name):
        f,s,o=self._s.get(name,(0,0,False)); return CircuitState(f,s,o)
    def allowed(self,name): return not self.state(name).open
    def snapshot(self): return {k:{'failures':f,'successes':s,'open':o} for k,(f,s,o) in sorted(self._s.items())}
