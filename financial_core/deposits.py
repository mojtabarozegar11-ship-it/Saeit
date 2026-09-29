from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DepositEvent:
    event_id: str
    user_id: str
    asset: str
    network: str
    amount: Decimal
    tx_hash: str
    confirmations: int


class DepositProcessor:
    """Credits only sufficiently confirmed deposits and prevents duplicate crediting."""
    def __init__(self, asset_registry, event_store, ledger_credit):
        self.assets = asset_registry
        self.event_store = event_store
        self.ledger_credit = ledger_credit

    def process(self, event: DepositEvent):
        if event.amount <= 0:
            return False, 'invalid-amount'
        asset = self.assets.get(event.asset, event.network)
        if not asset.deposits_enabled:
            return False, 'deposits-disabled'
        if event.confirmations < asset.min_confirmations:
            return False, 'awaiting-confirmations'
        unique_key = f'{event.network}:{event.tx_hash}:{event.event_id}'
        if self.event_store.exists(unique_key):
            return False, 'duplicate-event'
        # Event reservation must be atomic in the production store before ledger credit.
        if not self.event_store.reserve(unique_key):
            return False, 'duplicate-event'
        try:
            self.ledger_credit(event)
            self.event_store.commit(unique_key)
        except Exception:
            self.event_store.release(unique_key)
            raise
        return True, 'credited'
