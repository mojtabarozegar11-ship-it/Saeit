from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class WithdrawalLimits:
    max_single: Decimal

    def authorize(self, request):
        return request.amount > 0 and request.amount <= self.max_single
