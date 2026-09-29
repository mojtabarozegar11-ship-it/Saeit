from decimal import Decimal

from financial_core.agent_bridge import AgentFinancialRequest, FinancialAgentBridge
from financial_core.readiness import ProductionReadiness


def _audit(events):
    return lambda req, decision: events.append((req, decision))


def test_read_only_agent_access_works_before_real_mode():
    events=[]
    bridge=FinancialAgentBridge(ProductionReadiness(), lambda req: (True,''), _audit(events))
    d=bridge.authorize(AgentFinancialRequest('1','economic-master-agent','risk_snapshot'))
    assert d.allowed and d.execution_mode == 'read' and len(events)==1


def test_transactional_robot_is_blocked_until_financial_core_ready():
    bridge=FinancialAgentBridge(ProductionReadiness(), lambda req: (True,''), lambda *args: None)
    d=bridge.authorize(AgentFinancialRequest('1','economic-master-agent','trade','USDT',Decimal('10')))
    assert not d.allowed and d.reason == 'financial-production-not-ready'


def test_external_value_movement_requires_owner_approval():
    ready=ProductionReadiness(True,True,True,True,True,True,True)
    bridge=FinancialAgentBridge(ready, lambda req: (True,''), lambda *args: None)
    req=AgentFinancialRequest('1','economic-master-agent','transfer_funds','USDT',Decimal('10'))
    assert bridge.authorize(req).reason == 'owner-approval-required'
    approved=AgentFinancialRequest('2','economic-master-agent','transfer_funds','USDT',Decimal('10'),owner_approved=True)
    assert bridge.authorize(approved).allowed


def test_risk_engine_can_deny_agent_trade():
    ready=ProductionReadiness(True,True,True,True,True,True,True)
    bridge=FinancialAgentBridge(ready, lambda req: (False,'risk-limit'), lambda *args: None)
    d=bridge.authorize(AgentFinancialRequest('1','economic-master-agent','trade','BTC',Decimal('1')))
    assert not d.allowed and d.reason == 'risk-limit'
