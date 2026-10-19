from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from master_gen20.controller import Generation20Controller
from .contracts import ContractGuard

@dataclass(frozen=True)
class Generation24Run:
    ok: bool; value: Any; agreement: float; trace_valid: bool; accepted: int; contract_ok: bool

class Generation24Controller:
    """Opt-in Gen24 facade: preserves Gen20 semantics and adds a fail-closed output contract."""
    def __init__(self,min_agreement=.60,trace=None,normalizer=None,output_contract:Callable[[Any],bool]|None=None):
        self.base=Generation20Controller(min_agreement=min_agreement,trace=trace,normalizer=normalizer); self.output_contract=output_contract
    def run(self,candidates:dict[str,Callable[[],Any]],validator=None):
        base=self.base.run(candidates,validator)
        guarded=ContractGuard(post=self.output_contract).run(lambda value:value,value=base.value) if base.ok else None
        contract_ok=bool(guarded and guarded.ok)
        return Generation24Run(base.ok and contract_ok,base.value if contract_ok else None,base.agreement,base.trace_valid,base.accepted,contract_ok)
