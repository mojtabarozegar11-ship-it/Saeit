"""Reserve-backed reward accounting for the synthetic MOJ PROP offer.

All amounts are native TRX in SUN. The ledger never treats virtual account
principal as cash and never commits a reward before a settled customer payment.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


SUN_PER_TRX = 1_000_000
REWARD_RESERVE_BPS = 8_000
REFUND_RESERVE_BPS = 1_000
OPERATING_BUFFER_BPS = 1_000
BPS = 10_000


def _sun(value, name="amount_sun"):
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


@dataclass(frozen=True)
class ReserveAllocation:
    order_id: str
    fee_sun: int
    reward_reserve_sun: int
    refund_reserve_sun: int
    operating_buffer_sun: int
    maximum_reward_sun: int
    virtual_principal_requirement_sun: int = 0


class RewardReserveLedger:
    """In-memory contract model; persistence must be atomic before production."""

    def __init__(self):
        self.allocations = {}
        self.committed_rewards_sun = 0

    def allocate_after_settlement(self, *, order_id, fee_sun,
                                  settlement_confirmed):
        if not order_id:
            raise ValueError("order_id is required")
        if settlement_confirmed is not True:
            raise ValueError("settled_payment_required")
        if order_id in self.allocations:
            raise ValueError("duplicate_reserve_allocation")
        fee = _sun(fee_sun)
        reward = fee * REWARD_RESERVE_BPS // BPS
        refund = fee * REFUND_RESERVE_BPS // BPS
        operating = fee - reward - refund
        allocation = ReserveAllocation(
            order_id=order_id,
            fee_sun=fee,
            reward_reserve_sun=reward,
            refund_reserve_sun=refund,
            operating_buffer_sun=operating,
            maximum_reward_sun=reward,
        )
        self.allocations[order_id] = allocation
        return allocation

    @property
    def total_reward_reserve_sun(self):
        return sum(a.reward_reserve_sun for a in self.allocations.values())

    @property
    def available_reward_reserve_sun(self):
        return self.total_reward_reserve_sun - self.committed_rewards_sun

    def can_commit(self, amount_sun):
        amount = _sun(amount_sun)
        return amount <= self.available_reward_reserve_sun

    def commit_reward(self, *, order_id, amount_sun):
        if order_id not in self.allocations:
            raise ValueError("unknown_reserve_allocation")
        amount = _sun(amount_sun)
        if amount > self.allocations[order_id].maximum_reward_sun:
            raise ValueError("reward_exceeds_order_reserve")
        if not self.can_commit(amount):
            raise ValueError("reward_reserve_shortfall")
        self.committed_rewards_sun += amount
        return self.committed_rewards_sun

    def snapshot(self):
        return {
            "total_reward_reserve_sun": self.total_reward_reserve_sun,
            "committed_rewards_sun": self.committed_rewards_sun,
            "available_reward_reserve_sun": self.available_reward_reserve_sun,
            "virtual_principal_requirement_sun": 0,
        }
