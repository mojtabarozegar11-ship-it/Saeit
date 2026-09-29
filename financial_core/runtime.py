"""Runtime composition for the site's Financial section.

This module connects economic/financial agents to the guarded Financial Core.
It deliberately has no private-key handling and cannot make production ready
unless every external dependency reports healthy.
"""
from dataclasses import dataclass
from .readiness import ProductionReadiness
from .agent_bridge import FinancialAgentBridge


@dataclass(frozen=True)
class RuntimeHealth:
    persistent_ledger: bool
    custody_connected: bool
    blockchain_connectors_healthy: bool
    compliance_connected: bool
    reconciliation_healthy: bool
    security_review_passed: bool
    owner_approved: bool

    def readiness(self):
        return ProductionReadiness(
            self.persistent_ledger,
            self.custody_connected,
            self.blockchain_connectors_healthy,
            self.compliance_connected,
            self.reconciliation_healthy,
            self.security_review_passed,
            self.owner_approved,
        )


class FinancialRuntime:
    def __init__(self, health_provider, risk_authorizer, audit_sink):
        self.health_provider = health_provider
        self.risk_authorizer = risk_authorizer
        self.audit_sink = audit_sink

    def readiness(self):
        health = self.health_provider()
        if not isinstance(health, RuntimeHealth):
            return ProductionReadiness()
        return health.readiness()

    def agent_bridge(self):
        return FinancialAgentBridge(self.readiness(), self.risk_authorizer, self.audit_sink)

    def status(self):
        ready = self.readiness()
        return {
            'financial_core': 'ready' if ready.ready else 'guarded',
            'agent_read_access': True,
            'agent_real_execution': ready.ready,
            'custody_keys_exposed_to_agents': False,
        }
