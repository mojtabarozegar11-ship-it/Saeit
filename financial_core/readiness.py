from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionReadiness:
    persistent_ledger: bool = False
    custody_connected: bool = False
    blockchain_connectors_healthy: bool = False
    compliance_connected: bool = False
    reconciliation_healthy: bool = False
    security_review_passed: bool = False
    owner_approved: bool = False

    @property
    def ready(self):
        return all((
            self.persistent_ledger,
            self.custody_connected,
            self.blockchain_connectors_healthy,
            self.compliance_connected,
            self.reconciliation_healthy,
            self.security_review_passed,
            self.owner_approved,
        ))

    def require_ready(self):
        if not self.ready:
            raise RuntimeError('financial-production-not-ready')
        return True
