"""LiteFinance adapter boundary.

No credentials are stored here. Live transport must be injected from environment/secret storage.
Real execution remains disabled until an approved transport is configured and the RiskGate real policy is explicitly enabled.
"""
from ..execution import Connector

class LiteFinanceConnector(Connector):
    def __init__(self, transport=None): self.transport=transport
    def execute(self, request):
        if self.transport is None: raise RuntimeError('LiteFinance transport not configured')
        return self.transport.execute(request)
