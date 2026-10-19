from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CircuitState:
    failures:int=0
    open_until:int=0

class DeterministicCircuitBreaker:
    """Gen31: deterministic circuit breaker; caller supplies monotonic ticks, making behavior testable/replayable."""
    def __init__(self,failure_threshold=3,cooldown_ticks=5):
        if failure_threshold<1 or cooldown_ticks<1: raise ValueError('positive thresholds required')
        self.threshold=int(failure_threshold); self.cooldown=int(cooldown_ticks); self._state={}
    def allow(self,name:str,tick:int): return int(tick)>=self._state.get(name,CircuitState()).open_until
    def record(self,name:str,ok:bool,tick:int):
        old=self._state.get(name,CircuitState())
        if ok: new=CircuitState()
        else:
            f=old.failures+1; new=CircuitState(0,int(tick)+self.cooldown) if f>=self.threshold else CircuitState(f,old.open_until)
        self._state[name]=new; return new
    def state(self,name:str): return self._state.get(name,CircuitState())
