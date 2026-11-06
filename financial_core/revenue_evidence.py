"""Fail-closed evidence gate for trader-agent customer revenue.

Trading P&L is intentionally a different ledger from customer revenue. This
pure module only validates evidence; it never charges, settles, transfers,
publishes, or places an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class RevenueEvidenceError(ValueError):
    """Raised when a customer-revenue fact cannot be independently verified."""


@dataclass(frozen=True)
class CustomerRevenueEvidence:
    order_id: str
    payment_reference: str
    settlement_reference: str
    provider: str
    currency: str
    amount: Decimal
    settled_at: datetime
    independently_reconciled: bool
    source_record: str


@dataclass(frozen=True)
class VerifiedRevenueFact:
    order_id: str
    provider: str
    currency: str
    amount: Decimal
    settlement_reference: str
    settled_at: datetime
    verified: bool = True
    ledger: str = "customer_revenue"
    trading_pnl_included: bool = False


def verify_customer_revenue(evidence: CustomerRevenueEvidence) -> VerifiedRevenueFact:
    """Return a revenue fact only after all independent settlement gates pass."""
    required = {
        "order_id": evidence.order_id,
        "payment_reference": evidence.payment_reference,
        "settlement_reference": evidence.settlement_reference,
        "provider": evidence.provider,
        "currency": evidence.currency,
        "source_record": evidence.source_record,
    }
    if any(not isinstance(value, str) or not value.strip() for value in required.values()):
        raise RevenueEvidenceError("required_settlement_evidence_missing")
    if evidence.amount <= Decimal("0"):
        raise RevenueEvidenceError("settled_amount_must_be_positive")
    if evidence.currency.strip().upper() != evidence.currency.strip():
        raise RevenueEvidenceError("currency_must_be_canonical_uppercase")
    if evidence.settled_at.tzinfo is None:
        raise RevenueEvidenceError("settled_at_must_be_timezone_aware")
    if not evidence.independently_reconciled:
        raise RevenueEvidenceError("independent_reconciliation_required")
    return VerifiedRevenueFact(
        order_id=evidence.order_id.strip(),
        provider=evidence.provider.strip(),
        currency=evidence.currency.strip(),
        amount=evidence.amount,
        settlement_reference=evidence.settlement_reference.strip(),
        settled_at=evidence.settled_at,
    )
