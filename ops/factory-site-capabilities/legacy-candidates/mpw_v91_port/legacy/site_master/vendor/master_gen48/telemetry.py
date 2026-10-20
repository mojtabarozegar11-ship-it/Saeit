from __future__ import annotations
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class LatencySummary:
    count:int; mean_ms:float; p95_ms:float; failures:int

class RuntimeTelemetry:
    """Gen45: bounded in-process runtime telemetry for latency/error evidence."""
    def __init__(self,max_samples=512): self.max=max(8,int(max_samples)); self._rows={}
    def observe(self,name,latency_ms,ok):
        rows=self._rows.setdefault(name,[]); rows.append((max(0.0,float(latency_ms)),bool(ok))); del rows[:-self.max]; return self.summary(name)
    def summary(self,name):
        rows=self._rows.get(name,[])
        if not rows:return LatencySummary(0,0.0,0.0,0)
        vals=sorted(x for x,_ in rows); idx=max(0,min(len(vals)-1,ceil(.95*len(vals))-1))
        return LatencySummary(len(rows),sum(vals)/len(vals),vals[idx],sum(1 for _,ok in rows if not ok))
    def snapshot(self): return {k:[list(x) for x in v] for k,v in sorted(self._rows.items())}
