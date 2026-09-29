from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

@dataclass(frozen=True)
class Posting:
    account: str; amount: Decimal; asset: str='USD'
@dataclass(frozen=True)
class JournalEntry:
    id: str; postings: tuple[Posting, ...]; memo: str=''
    def validate(self):
        totals={}
        for p in self.postings: totals[p.asset]=totals.get(p.asset,Decimal('0'))+p.amount
        if any(v != 0 for v in totals.values()): raise ValueError('unbalanced journal entry')

class Ledger:
    def __init__(self): self._entries=[]; self._ids=set()
    def post(self, entry: JournalEntry):
        entry.validate()
        if entry.id in self._ids: return False
        self._entries.append(entry); self._ids.add(entry.id); return True
    def balance(self, account, asset='USD'):
        return sum((p.amount for e in self._entries for p in e.postings if p.account==account and p.asset==asset), Decimal('0'))
    @property
    def entries(self): return tuple(self._entries)
