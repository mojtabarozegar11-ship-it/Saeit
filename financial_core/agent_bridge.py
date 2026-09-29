"""Guarded bridge between economic/financial robots and Financial Core.

Agents may propose transactions, but they never receive custody keys and never
broadcast directly. Transactional execution is gated by production readiness,
risk policy, audit identity and owner approval where required.
"""
from dataclasses import dataclass
from decimal import Decimal


READ_ONLY_ACTIONS = frozenset({
    'balance', 'positions', 'market_data', 'quote', 'risk_snapshot',
    'reconciliation_status', 'reserve_status', 'report',
})
TRANSACTIONAL_ACTIONS = frozenset({
    'buy', 'sell', 'trade', 'rebalance', 'payment', 'transfer_funds',
    'place_order', 'settle',
})


@dataclass(frozen=True)
class AgentFinancialRequest:
    request_id: str
    agent_code: str
    action: str
    asset: str = ''
    amount: Decimal = Decimal('0')
    destination: str = ''
    owner_approved: bool = False


@dataclass(frozen=True)
class AgentFinancialDecision:
    request_id: str
    allowed: bool
    reason: str
    execution_mode: str = 'none'


class FinancialAgentBridge:
    def __init__(self, readiness, risk_authorizer, audit_sink):
        self.readiness = readiness
        self.risk_authorizer = risk_authorizer
        self.audit_sink = audit_sink

    def authorize(self, request: AgentFinancialRequest):
        action = str(request.action or '').strip().lower()
        if action in READ_ONLY_ACTIONS:
            decision = AgentFinancialDecision(request.request_id, True, 'read-only', 'read')
            self.audit_sink(request, decision)
            return decision
        if action not in TRANSACTIONAL_ACTIONS:
            decision = AgentFinancialDecision(request.request_id, False, 'unsupported-action')
            self.audit_sink(request, decision)
            return decision
        if not self.readiness.ready:
            decision = AgentFinancialDecision(request.request_id, False, 'financial-production-not-ready')
            self.audit_sink(request, decision)
            return decision
        if request.amount <= 0:
            decision = AgentFinancialDecision(request.request_id, False, 'invalid-amount')
            self.audit_sink(request, decision)
            return decision
        ok, reason = self.risk_authorizer(request)
        if not ok:
            decision = AgentFinancialDecision(request.request_id, False, reason or 'risk-denied')
            self.audit_sink(request, decision)
            return decision
        if action in {'payment', 'transfer_funds', 'settle'} and not request.owner_approved:
            decision = AgentFinancialDecision(request.request_id, False, 'owner-approval-required')
            self.audit_sink(request, decision)
            return decision
        decision = AgentFinancialDecision(request.request_id, True, 'authorized', 'guarded-real')
        self.audit_sink(request, decision)
        return decision
