"""Verified revenue lifecycle for the existing Saeit Master Agent.

This module deliberately does not move money. It defines the canonical states
and the evidence gate that every revenue-producing workflow must satisfy before
it may be counted as verified revenue.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Mapping, Optional


class RevenueState(str, Enum):
    OPPORTUNITY = "opportunity"
    QUALIFIED = "qualified"
    APPROVED = "approved"
    EXECUTING = "executing"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    PAID = "paid"
    SETTLED = "settled"
    VERIFIED = "verified_revenue"


REVENUE_STATE_ORDER = tuple(RevenueState)


@dataclass(frozen=True)
class SettlementEvidence:
    provider: str
    external_reference: str
    amount: Decimal
    currency: str
    settled_at: str
    reconciliation_reference: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def is_complete(self) -> bool:
        return all((
            self.provider.strip(),
            self.external_reference.strip(),
            self.amount > 0,
            self.currency.strip(),
            self.settled_at.strip(),
            self.reconciliation_reference.strip(),
        ))


def may_mark_verified(state: RevenueState, evidence: Optional[SettlementEvidence]) -> bool:
    """Only externally evidenced, reconciled settlement can become verified revenue."""
    return state == RevenueState.SETTLED and evidence is not None and evidence.is_complete()


def next_state(current: RevenueState) -> Optional[RevenueState]:
    index = REVENUE_STATE_ORDER.index(current)
    if index + 1 >= len(REVENUE_STATE_ORDER):
        return None
    return REVENUE_STATE_ORDER[index + 1]
