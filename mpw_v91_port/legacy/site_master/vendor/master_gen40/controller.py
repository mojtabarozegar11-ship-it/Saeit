from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from master_gen32 import Generation32Controller
from .uncertainty import UncertaintyCalibrator
from .diversity import DiversityPortfolio
from .journal import IdempotentJournal
from .deadline import DeadlinePlanner
from .replay import DeterministicReplayLedger
from .state import VersionedStateStore

@dataclass(frozen=True)
class Generation40Run:
    base: Any; idempotent_replay: bool; journal_valid: bool; ledger_valid: bool; selected: tuple[str,...]
    @property
    def ok(self): return bool(self.base.ok)
    @property
    def value(self): return self.base.value

class Generation40Controller:
    """Gen40 additive facade over Gen32: conservative + diverse + deadline-aware + idempotent + auditable."""
    def __init__(self,**gen32_kwargs):
        self.base=Generation32Controller(**gen32_kwargs); self.uncertainty=UncertaintyCalibrator(); self.diversity=DiversityPortfolio(); self.journal=IdempotentJournal(); self.deadlines=DeadlinePlanner(); self.ledger=DeterministicReplayLedger(); self.state=VersionedStateStore()
    def run(self,candidates:dict[str,Callable[[],Any]],request_id:str,domains=None,latency_ms=None,deadline_ms=None,min_candidates=1,max_candidates=None,**kwargs):
        names=tuple(candidates); scores={n:self.uncertainty.conservative_score(n) for n in names}
        selected=self.diversity.select(names,scores,domains,limit=max_candidates or len(names)).selected
        if deadline_ms is not None:
            plan=self.deadlines.plan(selected,latency_ms or {},deadline_ms,min_candidates,max_candidates)
            if not plan.within_deadline: raise ValueError('deadline cannot satisfy minimum candidates')
            selected=plan.selected
        if len(selected)<int(min_candidates): raise ValueError('insufficient selected candidates')
        subset={n:candidates[n] for n in selected}; executed=False
        def invoke():
            nonlocal executed; executed=True
            result=self.base.run(subset,min_candidates=min_candidates,max_candidates=max_candidates,**kwargs)
            for n in result.attempted: self.uncertainty.observe(n,1.0 if result.ok else 0.0)
            return result
        result,created=self.journal.execute(str(request_id),invoke)
        self.ledger.append({'request_id':str(request_id),'selected':selected,'created':created,'ok':bool(result.ok)})
        return Generation40Run(result,not created,self.journal.verify(),self.ledger.verify(),tuple(selected))
    def snapshot(self):
        return self.state.commit({'registry':self.base.registry.snapshot(),'uncertainty':self.uncertainty.snapshot(),'journal':self.journal.snapshot(),'ledger':self.ledger.events()})
