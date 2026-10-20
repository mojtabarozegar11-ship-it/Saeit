from __future__ import annotations
from dataclasses import dataclass
from time import monotonic

@dataclass(frozen=True)
class CacheReport:
    hits:int; misses:int; size:int; hit_rate:float

class AdaptiveResultCache:
    """Gen52: bounded TTL cache for explicitly cache-safe/idempotent request paths."""
    def __init__(self,max_entries=256,ttl_s=60): self.max=max(1,int(max_entries)); self.ttl=max(0.0,float(ttl_s)); self._d={}; self.hits=0; self.misses=0
    def get(self,key):
        row=self._d.get(key); now=monotonic()
        if row and now-row[0]<=self.ttl: self.hits+=1; return True,row[1]
        self.misses+=1; self._d.pop(key,None); return False,None
    def put(self,key,value):
        self._d[key]=(monotonic(),value)
        while len(self._d)>self.max: self._d.pop(next(iter(self._d)))
    def report(self):
        n=self.hits+self.misses; return CacheReport(self.hits,self.misses,len(self._d),self.hits/n if n else 0.0)
