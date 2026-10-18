from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OutcomeEstimate:
    mean:float; observations:int

class OutcomeLearner:
    """Gen54: conservative online outcome learning used only by the opt-in Gen56 selector."""
    def __init__(self,prior=.5,prior_weight=2): self.prior=float(prior); self.weight=max(0.0,float(prior_weight)); self._s={}
    def observe(self,name,quality):
        n,total=self._s.get(name,(0,0.0)); q=max(0.0,min(1.0,float(quality))); self._s[name]=(n+1,total+q); return self.estimate(name)
    def estimate(self,name):
        n,total=self._s.get(name,(0,0.0)); den=n+self.weight; return OutcomeEstimate((total+self.prior*self.weight)/den if den else self.prior,n)
    def snapshot(self): return {k:{'n':n,'sum':s} for k,(n,s) in sorted(self._s.items())}
