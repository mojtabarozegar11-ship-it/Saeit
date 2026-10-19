from __future__ import annotations
import copy, hashlib, json
from dataclasses import dataclass

@dataclass(frozen=True)
class DurableCheckpoint:
    version:int; digest:str; payload:dict

class CheckpointCodec:
    """Gen46: portable, integrity-checked checkpoint encoding/decoding."""
    @staticmethod
    def _digest(version,payload): return hashlib.sha256(json.dumps({'version':version,'payload':payload},sort_keys=True,separators=(',',':'),default=repr).encode()).hexdigest()
    def encode(self,version,payload):
        p=copy.deepcopy(payload); return DurableCheckpoint(int(version),self._digest(int(version),p),p)
    def verify(self,c): return c.digest==self._digest(c.version,c.payload)
    def decode(self,c):
        if not self.verify(c): raise ValueError('checkpoint integrity failure')
        return copy.deepcopy(c.payload)
