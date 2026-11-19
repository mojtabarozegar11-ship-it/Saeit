"""Fail-closed boundary between risk review, reservation and broker acknowledgement.

The boundary can create an internal reservation and can record a broker order
reference only after an independently authenticated adapter reports that
permission evidence exists.  It never submits an order and has no network
client.  This keeps a future LiteFinance adapter behind a visible, testable
authority boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from .plan1_shared_owner_risk import RiskPreview
from .plan1_owner_reservations import Reservation, ReservationLedger


class BoundaryError(Exception):
    """Base class for fail-closed boundary errors."""


class ReviewDenied(BoundaryError):
    """The risk review rejected the proposed order."""


class MissingBrokerEvidence(BoundaryError):
    """The trusted adapter evidence is incomplete."""


class ExecutionDisabled(BoundaryError):
    """No broker submission authority exists in this source-only boundary."""


@dataclass(frozen=True)
class BrokerPermissionEvidence:
    broker_contract_verified: bool
    demo_reconciliation_verified: bool
    live_execution_authorized: bool

    def complete_for_ack(self) -> bool:
        return (
            self.broker_contract_verified is True
            and self.demo_reconciliation_verified is True
            and self.live_execution_authorized is True
        )


@dataclass(frozen=True)
class BoundaryResult:
    reservation: Reservation
    execution_submitted: bool = False


class OwnerAccountExecutionBoundary:
    """Connects the review result to the ledger without executing trades."""

    def __init__(self, ledger: ReservationLedger):
        self.ledger = ledger

    def reserve_reviewed_order(
        self, *, review: RiskPreview, reservation_id: str,
        idempotency_key: str, account_ref: str, trader_ref: str,
        proposed_margin_usd: Decimal, order_ref: str | None = None,
    ) -> BoundaryResult:
        if type(review) is not RiskPreview:
            raise TypeError("exact RiskPreview required")
        if review.review_allowed is not True:
            raise ReviewDenied("risk review is not approved")
        trader_capital = (
            review.trader_aggregate_limit_usd / Decimal("0.016")
        )
        account_capital = (
            review.account_aggregate_limit_usd / Decimal("0.016")
        )
        reservation = self.ledger.reserve(
            reservation_id=reservation_id,
            idempotency_key=idempotency_key,
            account_ref=account_ref,
            trader_ref=trader_ref,
            capital_usd=trader_capital,
            risk_usd=review.proposed_order_risk_usd,
            margin_usd=proposed_margin_usd,
            max_account_risk_usd=review.account_aggregate_limit_usd,
            max_trader_risk_usd=review.trader_aggregate_limit_usd,
            max_account_capital_usd=account_capital,
            order_ref=order_ref,
        )
        return BoundaryResult(reservation=reservation)

    def record_trusted_broker_ack(
        self, *, reservation_id: str, broker_order_ref: str,
        evidence: BrokerPermissionEvidence,
    ) -> BoundaryResult:
        if type(evidence) is not BrokerPermissionEvidence:
            raise TypeError("exact BrokerPermissionEvidence required")
        if not evidence.complete_for_ack():
            raise MissingBrokerEvidence("broker permission evidence incomplete")
        reservation = self.ledger.bind_broker_order(
            reservation_id=reservation_id,
            broker_order_ref=broker_order_ref,
        )
        return BoundaryResult(reservation=reservation)

    def submit_to_broker(self, *_: Any, **__: Any) -> None:
        raise ExecutionDisabled(
            "broker adapter is not wired; no order submission authority"
        )

    def make_submitter(self) -> Callable[..., None]:
        """Return an explicit disabled callable for UI/service integration."""
        return self.submit_to_broker
