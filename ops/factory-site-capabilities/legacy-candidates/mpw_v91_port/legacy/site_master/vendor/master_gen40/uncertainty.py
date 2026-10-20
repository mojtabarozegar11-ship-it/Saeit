from __future__ import annotations
from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class ConfidenceBand:
    mean: float
    lower: float
    upper: float
    samples: int

class UncertaintyCalibrator:
    """Gen33: bounded online quality moments and conservative confidence bands."""
    def __init__(self, prior_mean=.5, prior_weight=2.0):
        self.prior_mean=float(prior_mean); self.prior_weight=max(0.0,float(prior_weight)); self._rows={}
    def observe(self,name:str,quality:float):
        q=max(0.0,min(1.0,float(quality))); n,s,ss=self._rows.get(name,(0,0.0,0.0)); self._rows[name]=(n+1,s+q,ss+q*q); return self.band(name)
    def band(self,name:str,z=1.0):
        n,s,ss=self._rows.get(name,(0,0.0,0.0)); w=n+self.prior_weight
        mean=(s+self.prior_mean*self.prior_weight)/w if w else self.prior_mean
        if n>1:
            raw=s/n; var=max(0.0,(ss-n*raw*raw)/(n-1)); se=sqrt(var/n)
        else: se=.25/sqrt(max(1.0,w))
        d=float(z)*se; return ConfidenceBand(mean,max(0.0,mean-d),min(1.0,mean+d),n)
    def conservative_score(self,name:str,z=1.0): return self.band(name,z).lower
    def snapshot(self): return {k:{'n':n,'sum':s,'sum_sq':ss} for k,(n,s,ss) in sorted(self._rows.items())}
