from dataclasses import dataclass
from decimal import Decimal
from .domain import Environment

@dataclass(frozen=True)
class ExecutionRequest:
    id: str; environment: Environment; notional: Decimal; worst_case_loss: Decimal; action: str

@dataclass
class RiskPolicy:
    max_demo_notional: Decimal=Decimal('100000')
    max_real_notional: Decimal=Decimal('0')
    max_real_loss: Decimal=Decimal('0')
    real_enabled: bool=False

class RiskGate:
    def __init__(self, policy=None): self.policy=policy or RiskPolicy()
    def authorize(self, req, owner_approved=False):
        if req.notional < 0 or req.worst_case_loss < 0: return False, 'invalid-risk-values'
        if req.environment is Environment.DEMO:
            return (req.notional <= self.policy.max_demo_notional, 'demo-limit')
        if not self.policy.real_enabled: return False, 'real-locked'
        if not owner_approved: return False, 'owner-approval-required'
        if req.notional > self.policy.max_real_notional or req.worst_case_loss > self.policy.max_real_loss: return False, 'real-limit'
        return True, 'authorized'
