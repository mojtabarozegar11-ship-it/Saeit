from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from time import monotonic
from typing import Any, Callable

@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    writes: int
    evictions: int

class TaskResultCache:
    """Bounded, thread-safe opt-in result cache for deterministic/idempotent capabilities."""
    def __init__(self, max_entries: int = 1024, ttl_seconds: float | None = 300.0):
        self.max_entries=max(1,int(max_entries)); self.ttl_seconds=ttl_seconds
        self._data: dict[str, tuple[float, Any]]={}; self._lock=RLock()
        self._hits=self._misses=self._writes=self._evictions=0

    @staticmethod
    def fingerprint(namespace: str, payload: Any) -> str:
        raw=json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False, default=repr)
        return sha256((namespace+"\0"+raw).encode("utf-8")).hexdigest()

    def get(self, key: str):
        with self._lock:
            row=self._data.get(key)
            if row is None: self._misses+=1; return None
            created,value=row
            if self.ttl_seconds is not None and monotonic()-created > self.ttl_seconds:
                del self._data[key]; self._evictions+=1; self._misses+=1; return None
            self._hits+=1; return value

    def put(self, key: str, value: Any):
        with self._lock:
            if key not in self._data and len(self._data) >= self.max_entries:
                oldest=min(self._data, key=lambda k:self._data[k][0]); del self._data[oldest]; self._evictions+=1
            self._data[key]=(monotonic(),value); self._writes+=1
        return value

    def compute(self, namespace: str, payload: Any, fn: Callable[[], Any]):
        key=self.fingerprint(namespace,payload); cached=self.get(key)
        if cached is not None: return cached, True
        return self.put(key,fn()), False

    def stats(self): return CacheStats(self._hits,self._misses,self._writes,self._evictions)
