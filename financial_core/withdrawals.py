from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class WithdrawalState(str, Enum):
    REQUESTED='requested'
    REVIEW='review'
    APPROVED='approved'
    BROADCAST='broadcast'
    CONFIRMED='confirmed'
    REJECTED='rejected'

@dataclass(frozen=True)
class WithdrawalRequest:
    id: str
    user_id: str
    asset: str
    network: str
    amount: Decimal
    destination: str

@dataclass(frozen=True)
class WithdrawalDecision:
    request_id: str
    state: WithdrawalState
    reason: str = ''

class WithdrawalGate:
    """Fail-closed gate. Blockchain broadcast belongs in an audited connector."""
    def __init__(self, asset_registry, compliance, limits):
        self.assets = asset_registry
        self.compliance = compliance
        self.limits = limits

    def review(self, req: WithdrawalRequest, owner_approved=False):
        if req.amount <= 0:
            return WithdrawalDecision(req.id, WithdrawalState.REJECTED, 'invalid-amount')
        asset = self.assets.get(req.asset, req.network)
        if not asset.withdrawals_enabled:
            return WithdrawalDecision(req.id, WithdrawalState.REJECTED, 'withdrawals-disabled')
        if req.amount < asset.min_withdrawal:
            return WithdrawalDecision(req.id, WithdrawalState.REJECTED, 'below-minimum')
        ok, reason = self.compliance.authorize_withdrawal(req)
        if not ok:
            return WithdrawalDecision(req.id, WithdrawalState.REJECTED, reason)
        if not self.limits.authorize(req):
            return WithdrawalDecision(req.id, WithdrawalState.REVIEW, 'limit-review')
        if not owner_approved:
            return WithdrawalDecision(req.id, WithdrawalState.REVIEW, 'owner-approval-required')
        return WithdrawalDecision(req.id, WithdrawalState.APPROVED)
