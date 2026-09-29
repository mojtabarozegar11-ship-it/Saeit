from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class Asset:
    symbol: str
    network: str
    decimals: int
    min_confirmations: int
    withdrawals_enabled: bool = False
    deposits_enabled: bool = False
    min_withdrawal: Decimal = Decimal('0')

class AssetRegistry:
    def __init__(self, assets=()):
        self._assets = {(a.symbol.upper(), a.network.lower()): a for a in assets}

    def get(self, symbol: str, network: str) -> Asset:
        key = (symbol.upper(), network.lower())
        if key not in self._assets:
            raise KeyError(f'unsupported asset/network: {symbol}/{network}')
        return self._assets[key]

    def enabled_for_deposit(self):
        return tuple(a for a in self._assets.values() if a.deposits_enabled)

    def enabled_for_withdrawal(self):
        return tuple(a for a in self._assets.values() if a.withdrawals_enabled)
