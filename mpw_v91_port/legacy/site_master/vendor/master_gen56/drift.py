from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from statistics import fmean

@dataclass(frozen=True)
class DriftReport:
    drifted:bool; reference_mean:float; recent_mean:float; relative_change:float

class DriftDetector:
    """Gen53: bounded two-window drift detection for quality/latency signals."""
    def __init__(self,window=8,threshold=.25): self.window=max(2,int(window)); self.threshold=max(0.0,float(threshold)); self._x=deque(maxlen=2*self.window)
    def observe(self,value): self._x.append(float(value)); return self.report()
    def report(self):
        if len(self._x)<2*self.window: return DriftReport(False,0.0,0.0,0.0)
        x=list(self._x); a=fmean(x[:self.window]); b=fmean(x[self.window:]); d=(b-a)/abs(a) if a else (1.0 if b else 0.0)
        return DriftReport(abs(d)>=self.threshold,a,b,d)
