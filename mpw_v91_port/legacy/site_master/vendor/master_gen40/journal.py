from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any, Callable

@dataclass(frozen=True)
class JournalEntry:
    sequence:int; key:str; status:str; value_hash:str

class IdempotentJournal:
    """Gen35: in-memory deterministic idempotency + tamper-evident execution journal."""
    def __init__(self): self._values={}; self._entries=[]
    @staticmethod
    def _hash(value:Any):
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),default=repr).encode(); return hashlib.sha256(raw).hexdigest()
    def execute(self,key:str,fn:Callable[[],Any]):
        if key in self._values: return self._values[key],False
        try: value=fn(); status='committed'
        except Exception:
            self._entries.append(JournalEntry(len(self._entries)+1,key,'failed','')); raise
        self._values[key]=value; self._entries.append(JournalEntry(len(self._entries)+1,key,status,self._hash(value))); return value,True
    def entries(self): return tuple(self._entries)
    def verify(self):
        return all(e.sequence==i+1 and (e.status!='committed' or e.value_hash==self._hash(self._values[e.key])) for i,e in enumerate(self._entries))
    def snapshot(self): return {'values':dict(self._values),'entries':[asdict(e) for e in self._entries]}
    @classmethod
    def restore(cls,data):
        obj=cls(); obj._values=dict(data.get('values',{})); obj._entries=[JournalEntry(**x) for x in data.get('entries',[])]; return obj
