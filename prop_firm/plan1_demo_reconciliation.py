"""Pure, read-only reconciliation for LiteFinance demo evidence.

The reconciler compares independently supplied demo evidence with the internal
reservation-to-trader map. It never writes a ledger row, contacts a broker,
submits an order, or treats a successful reconciliation as live permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .plan1_litefinance_demo_contract import (
    DemoAccountSnapshot,
    DemoExecutionReport,
    LiteFinanceDemoEvidenceContract,
)


class ReconciliationError(Exception):
    """Base class for deterministic reconciliation failures."""


class ReconciliationRejected(ReconciliationError):
    """Evidence cannot be reconciled without ambiguity."""


@dataclass(frozen=True)
class DemoReconciliationResult:
    verified: bool
    reasons: tuple[str, ...]
    broker_account_ref: str
    report_count: int
    verified_order_refs: tuple[str, ...]
    cancelled_order_refs: tuple[str, ...]


class LiteFinanceDemoReconciler:
    """Reconcile a bounded snapshot and report batch without side effects."""

    def __init__(self, contract: LiteFinanceDemoEvidenceContract):
        self.contract = contract

    def reconcile(
        self, *, snapshot: DemoAccountSnapshot,
        reports: tuple[DemoExecutionReport, ...],
        reservation_to_trader: Mapping[str, str],
    ) -> DemoReconciliationResult:
        if type(reports) is not tuple or len(reports) > 10000:
            raise TypeError("bounded tuple of reports required")
        if type(reservation_to_trader) is not dict:
            raise TypeError("server-side reservation map required")
        verified_snapshot = self.contract.validate_snapshot(snapshot)
        if not verified_snapshot.owner_account_ref:
            raise ReconciliationRejected("owner account reference missing")
        reasons: list[str] = []
        orders: set[str] = set()
        reservations: set[str] = set()
        verified_orders: list[str] = []
        cancelled_orders: list[str] = []
        for report in reports:
            if report.broker_order_ref in orders:
                reasons.append("duplicate_broker_order_reference")
                continue
            orders.add(report.broker_order_ref)
            expected_trader = reservation_to_trader.get(report.reservation_id)
            if expected_trader is None:
                reasons.append("reservation_not_in_server_map")
                continue
            if report.reservation_id in reservations:
                reasons.append("duplicate_reservation_reference")
                continue
            reservations.add(report.reservation_id)
            try:
                self.contract.validate_execution_report(
                    report,
                    expected_reservation_id=report.reservation_id,
                    expected_trader_ref=expected_trader,
                )
            except Exception as exc:
                reasons.append(type(exc).__name__)
                continue
            if report.status == "cancelled":
                cancelled_orders.append(report.broker_order_ref)
            else:
                verified_orders.append(report.broker_order_ref)
        return DemoReconciliationResult(
            verified=not reasons,
            reasons=tuple(reasons),
            broker_account_ref=verified_snapshot.broker_account_ref,
            report_count=len(reports),
            verified_order_refs=tuple(verified_orders),
            cancelled_order_refs=tuple(cancelled_orders),
        )
