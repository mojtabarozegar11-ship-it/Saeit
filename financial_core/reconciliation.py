"""Conservative asset-by-asset reconciliation; no transaction or custody writes."""
from dataclasses import dataclass
from decimal import Decimal
import re


@dataclass(frozen=True)
class ReserveSnapshot:
    asset: str
    customer_liability: Decimal
    treasury_assets: Decimal

    @property
    def valid(self):
        """Missing, negative, non-Decimal or non-finite inputs cannot prove cover."""
        return (isinstance(self.asset, str) and
                bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,39}", self.asset)) and
                all(isinstance(value, Decimal) and value.is_finite() and value >= 0
                    for value in (self.customer_liability, self.treasury_assets)))

    @property
    def surplus(self):
        if not self.valid:
            raise ValueError("invalid reserve snapshot; no surplus can be claimed")
        return self.treasury_assets - self.customer_liability

    @property
    def fully_reserved(self):
        return self.valid and self.surplus >= 0


class Reconciler:
    def verify(self, snapshots):
        """Return (covered, shortfalls); never certify an empty input collection.

        One independently reconciled record per asset is required. Duplicate
        snapshots could conceal liabilities or fabricate asset coverage.
        """
        snapshots = tuple(snapshots)
        if not snapshots:
            return False, ()
        seen = set()
        failures = []
        for snapshot in snapshots:
            if not isinstance(snapshot, ReserveSnapshot):
                raise ValueError("reserve snapshot type required")
            if snapshot.asset in seen:
                raise ValueError("duplicate reserve asset")
            seen.add(snapshot.asset)
            if not snapshot.fully_reserved:
                failures.append(snapshot)
        return len(failures) == 0, tuple(failures)
