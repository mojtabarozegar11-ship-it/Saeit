from __future__ import annotations
from dataclasses import dataclass
import copy

@dataclass(frozen=True)
class StateSnapshot:
    version:int; payload:dict

class VersionedStateStore:
    """Gen39: versioned copy-isolated snapshots with compare-and-swap restore semantics."""
    def __init__(self): self._version=0; self._payload={}
    def commit(self,payload:dict,expected_version:int|None=None):
        if expected_version is not None and int(expected_version)!=self._version: raise RuntimeError('state version conflict')
        self._version+=1; self._payload=copy.deepcopy(payload); return self.snapshot()
    def snapshot(self): return StateSnapshot(self._version,copy.deepcopy(self._payload))
    def restore(self,snapshot:StateSnapshot): self._version=int(snapshot.version); self._payload=copy.deepcopy(snapshot.payload); return self.snapshot()
