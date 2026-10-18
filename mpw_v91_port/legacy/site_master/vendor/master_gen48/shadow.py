from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ShadowReport:
    samples:int; wins:int; losses:int; ties:int; mean_delta:float

class ShadowEvaluator:
    """Gen47: paired baseline/candidate evaluation without changing production output."""
    def __init__(self): self._pairs=[]
    def observe(self,baseline,candidate): self._pairs.append((float(baseline),float(candidate))); return self.report()
    def report(self):
        ds=[c-b for b,c in self._pairs]; return ShadowReport(len(ds),sum(d>0 for d in ds),sum(d<0 for d in ds),sum(d==0 for d in ds),sum(ds)/len(ds) if ds else 0.0)
