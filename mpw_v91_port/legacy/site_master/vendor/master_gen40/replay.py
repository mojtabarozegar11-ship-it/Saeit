from __future__ import annotations
import hashlib, json

class DeterministicReplayLedger:
    """Gen38: hash-chained event ledger for deterministic audit/replay evidence."""
    def __init__(self): self._events=[]
    def append(self,event):
        payload=json.dumps(event,sort_keys=True,separators=(',',':'),default=repr); prev=self._events[-1]['hash'] if self._events else '0'*64
        digest=hashlib.sha256((prev+'|'+payload).encode()).hexdigest(); row={'index':len(self._events),'event':event,'prev':prev,'hash':digest}; self._events.append(row); return row
    def verify(self):
        prev='0'*64
        for i,row in enumerate(self._events):
            payload=json.dumps(row['event'],sort_keys=True,separators=(',',':'),default=repr); expected=hashlib.sha256((prev+'|'+payload).encode()).hexdigest()
            if row['index']!=i or row['prev']!=prev or row['hash']!=expected: return False
            prev=row['hash']
        return True
    def events(self): return tuple(dict(x) for x in self._events)
