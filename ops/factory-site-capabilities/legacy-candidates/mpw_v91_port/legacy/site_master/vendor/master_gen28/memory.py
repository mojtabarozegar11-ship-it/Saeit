from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any

@dataclass(frozen=True)
class MemoryRecord:
    key: str
    value: Any
    version: int
    digest: str

class DurableSemanticMemory:
    """Gen25: versioned, integrity-checked local memory with atomic persistence."""
    def __init__(self, path: str | Path):
        self.path=Path(path); self._lock=RLock()
    @staticmethod
    def _digest(key, value, version):
        raw=dumps({"key":key,"value":value,"version":version},sort_keys=True,separators=(",",":"),default=repr).encode()
        return sha256(raw).hexdigest()
    def _load(self):
        if not self.path.exists(): return {}
        data=loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("invalid memory store")
        for key,row in data.items():
            if row.get("digest") != self._digest(key,row.get("value"),row.get("version")): raise ValueError("memory integrity verification failed")
        return data
    def put(self,key:str,value:Any):
        with self._lock:
            data=self._load(); version=int(data.get(key,{}).get("version",0))+1; digest=self._digest(key,value,version)
            data[key]={"value":value,"version":version,"digest":digest}; self.path.parent.mkdir(parents=True,exist_ok=True)
            with NamedTemporaryFile("w",encoding="utf-8",dir=self.path.parent,delete=False) as f:
                f.write(dumps(data,sort_keys=True,ensure_ascii=False,default=repr)); tmp=Path(f.name)
            tmp.replace(self.path); return MemoryRecord(key,value,version,digest)
    def get(self,key:str,default=None):
        with self._lock:
            row=self._load().get(key)
            return default if row is None else row["value"]
    def snapshot(self):
        with self._lock:
            data=self._load(); return tuple(MemoryRecord(k,v["value"],v["version"],v["digest"]) for k,v in sorted(data.items()))
