from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from threading import RLock
from time import time
from typing import Any

@dataclass(frozen=True)
class TraceEvent:
    sequence: int
    timestamp: float
    kind: str
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str

class TamperEvidentTrace:
    """Gen13: bounded, thread-safe hash-chained trace for audit/replay evidence."""
    def __init__(self, max_events: int = 10_000):
        self.max_events=max(1,int(max_events)); self._events=[]; self._lock=RLock()

    @staticmethod
    def _digest(sequence, timestamp, kind, payload, previous_hash):
        body=json.dumps({"sequence":sequence,"timestamp":timestamp,"kind":kind,"payload":payload,
                         "previous_hash":previous_hash},sort_keys=True,separators=(",",":"),
                        ensure_ascii=False,default=repr)
        return sha256(body.encode("utf-8")).hexdigest()

    def append(self, kind: str, payload: dict[str, Any] | None=None):
        with self._lock:
            if len(self._events)>=self.max_events: raise OverflowError("trace capacity reached")
            sequence=len(self._events); timestamp=time(); previous=self._events[-1].event_hash if self._events else "0"*64
            clean=dict(payload or {}); digest=self._digest(sequence,timestamp,str(kind),clean,previous)
            event=TraceEvent(sequence,timestamp,str(kind),clean,previous,digest); self._events.append(event); return event

    def verify(self):
        with self._lock:
            previous="0"*64
            for i,event in enumerate(self._events):
                expected=self._digest(i,event.timestamp,event.kind,event.payload,previous)
                if event.sequence!=i or event.previous_hash!=previous or event.event_hash!=expected:
                    return {"valid":False,"events":len(self._events),"broken_at":i}
                previous=event.event_hash
            return {"valid":True,"events":len(self._events),"head":previous}

    def snapshot(self):
        with self._lock: return tuple(asdict(e) for e in self._events)
