from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class CanaryDecision:
    promote: bool; candidate_mean: float; baseline_mean: float; relative_gain: float; samples: int

class ShadowCanaryGate:
    """Gen36: paired shadow/canary evidence gate; never promotes without minimum real samples."""
    def __init__(self,required_gain=.40,min_samples=8): self.required=float(required_gain); self.minimum=max(1,int(min_samples)); self._pairs=[]
    def observe(self,baseline:float,candidate:float): self._pairs.append((float(baseline),float(candidate))); return self.decision()
    def decision(self):
        n=len(self._pairs)
        if not n: return CanaryDecision(False,0,0,0,0)
        b=sum(x for x,_ in self._pairs)/n; c=sum(y for _,y in self._pairs)/n; gain=(c-b)/abs(b) if b else (float('inf') if c>0 else 0.0)
        return CanaryDecision(n>=self.minimum and gain>=self.required,c,b,gain,n)
