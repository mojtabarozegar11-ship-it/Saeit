from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HealthState:
    score: float; quarantined: bool; observations: int

class CapabilityHealth:
    """Gen43: EWMA health tracking and automatic quarantine/recovery."""
    def __init__(self,alpha=.25,quarantine_below=.25,recover_above=.60): self.alpha=float(alpha); self.low=float(quarantine_below); self.high=float(recover_above); self._s={}
    def observe(self,name,ok:bool):
        score,q,n=self._s.get(name,(1.0,False,0)); score=(1-self.alpha)*score+self.alpha*(1.0 if ok else 0.0); q=(score<self.low) if not q else not(score>=self.high); self._s[name]=(score,q,n+1); return self.state(name)
    def state(self,name):
        s,q,n=self._s.get(name,(1.0,False,0)); return HealthState(s,q,n)
    def allowed(self,name): return not self.state(name).quarantined
    def snapshot(self): return {k:{'score':v[0],'quarantined':v[1],'observations':v[2]} for k,v in sorted(self._s.items())}
