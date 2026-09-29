from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import FrozenSet

class Environment(str, Enum):
    DEMO='demo'; REAL='real'
class UnitKind(str, Enum):
    AGENT='agent'; ROBOT='robot'
class UnitState(str, Enum):
    DRAFT='draft'; VALIDATING='validating'; ACTIVE='active'; PAUSED='paused'; RETIRED='retired'

@dataclass(frozen=True)
class Account:
    id: str; provider: str; environment: Environment; currency: str
    enabled: bool=False

@dataclass(frozen=True)
class UnitSpec:
    id: str; version: int; kind: UnitKind; mission: str
    tools: FrozenSet[str]=frozenset(); budget: Decimal=Decimal('0')
    max_loss: Decimal=Decimal('0'); real_money: bool=False

@dataclass
class UnitRuntime:
    spec: UnitSpec; state: UnitState=UnitState.DRAFT
    revenue: Decimal=Decimal('0'); cost: Decimal=Decimal('0')
    failures: int=0
    @property
    def profit(self): return self.revenue-self.cost
