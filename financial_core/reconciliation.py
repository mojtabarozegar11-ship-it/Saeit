from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class ReserveSnapshot:
    asset: str
    customer_liability: Decimal
    treasury_assets: Decimal

    @property
    def surplus(self):
        return self.treasury_assets - self.customer_liability

    @property
    def fully_reserved(self):
        return self.surplus >= 0

class Reconciler:
    def verify(self, snapshots):
        snapshots = tuple(snapshots)
        failures = tuple(s for s in snapshots if not s.fully_reserved)
        return len(failures) == 0, failures
