"""Tests for the source-only risk-to-reservation boundary."""
from decimal import Decimal as D
import os
import tempfile
import unittest

from prop_firm.plan1_execution_boundary import (
    BrokerPermissionEvidence, ExecutionDisabled, MissingBrokerEvidence,
    OwnerAccountExecutionBoundary, ReviewDenied,
)
from prop_firm.plan1_owner_reservations import ReservationLedger
from prop_firm.plan1_shared_owner_risk import RiskPreview


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(prefix="mojprop-boundary-", delete=False)
        self.tmp.close()
        self.ledger = ReservationLedger(self.tmp.name)
        self.boundary = OwnerAccountExecutionBoundary(self.ledger)
        self.review = RiskPreview(
            review_allowed=True,
            reasons=(),
            allocated_capital_usd=D("200"),
            aggregate_open_and_reserved_risk_usd=D("0.30"),
            proposed_order_risk_usd=D("0.80"),
            trader_order_limit_usd=D("0.80"),
            trader_aggregate_limit_usd=D("1.60"),
            account_aggregate_limit_usd=D("3.20"),
        )

    def tearDown(self):
        self.ledger.close()
        os.unlink(self.tmp.name)

    def reserve(self, **changes):
        values = dict(
            review=self.review,
            reservation_id="RES-001",
            idempotency_key="IDEM-001",
            account_ref="OWNER-LIVE",
            trader_ref="TRADER-A",
            proposed_margin_usd=D("10"),
            order_ref="ORDER-001",
        )
        values.update(changes)
        return self.boundary.reserve_reviewed_order(**values)

    def evidence(self, **changes):
        values = dict(
            broker_contract_verified=True,
            demo_reconciliation_verified=True,
            live_execution_authorized=True,
        )
        values.update(changes)
        return BrokerPermissionEvidence(**values)

    def test_approved_review_creates_internal_reservation_only(self):
        result = self.reserve()
        self.assertEqual(result.reservation.status, "reserved")
        self.assertFalse(result.execution_submitted)
        self.assertEqual(result.reservation.capital_usd, D("100"))

    def test_rejected_review_cannot_reserve(self):
        denied = RiskPreview(
            review_allowed=False,
            reasons=("trader_single_order_limit",),
            allocated_capital_usd=D("200"),
            aggregate_open_and_reserved_risk_usd=D("0.30"),
            proposed_order_risk_usd=D("0.81"),
            trader_order_limit_usd=D("0.80"),
            trader_aggregate_limit_usd=D("1.60"),
            account_aggregate_limit_usd=D("3.20"),
        )
        with self.assertRaises(ReviewDenied):
            self.reserve(review=denied)

    def test_preview_is_required_not_a_boolean(self):
        with self.assertRaises(TypeError):
            self.reserve(review=True)

    def test_reservation_preserves_trader_attribution(self):
        result = self.reserve(trader_ref="TRADER-B")
        self.assertEqual(result.reservation.trader_ref, "TRADER-B")
        self.assertEqual(
            self.ledger.exposure("OWNER-LIVE", "TRADER-B").reservation_count, 1
        )

    def test_margin_is_passed_to_ledger(self):
        result = self.reserve(proposed_margin_usd=D("12"))
        self.assertEqual(result.reservation.margin_usd, D("12"))

    def test_reservation_retry_is_idempotent_through_boundary(self):
        first = self.reserve()
        second = self.reserve()
        self.assertEqual(first, second)

    def test_submitter_is_explicitly_disabled(self):
        with self.assertRaises(ExecutionDisabled):
            self.boundary.submit_to_broker(symbol="XAUUSD")

    def test_submitter_factory_is_disabled(self):
        with self.assertRaises(ExecutionDisabled):
            self.boundary.make_submitter()()

    def test_incomplete_broker_contract_blocks_ack(self):
        self.reserve()
        with self.assertRaises(MissingBrokerEvidence):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-001",
                broker_order_ref="BROKER-001",
                evidence=self.evidence(broker_contract_verified=False),
            )

    def test_missing_demo_reconciliation_blocks_ack(self):
        self.reserve()
        with self.assertRaises(MissingBrokerEvidence):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-001",
                broker_order_ref="BROKER-001",
                evidence=self.evidence(demo_reconciliation_verified=False),
            )

    def test_missing_live_permission_blocks_ack(self):
        self.reserve()
        with self.assertRaises(MissingBrokerEvidence):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-001",
                broker_order_ref="BROKER-001",
                evidence=self.evidence(live_execution_authorized=False),
            )

    def test_boolean_impostor_is_not_permission(self):
        self.reserve()
        with self.assertRaises(MissingBrokerEvidence):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-001",
                broker_order_ref="BROKER-001",
                evidence=self.evidence(live_execution_authorized=1),
            )

    def test_complete_evidence_only_records_ack(self):
        self.reserve()
        result = self.boundary.record_trusted_broker_ack(
            reservation_id="RES-001",
            broker_order_ref="BROKER-001",
            evidence=self.evidence(),
        )
        self.assertEqual(result.reservation.status, "submitted")
        self.assertFalse(result.execution_submitted)

    def test_ack_is_idempotent_for_same_broker_reference(self):
        self.reserve()
        first = self.boundary.record_trusted_broker_ack(
            reservation_id="RES-001",
            broker_order_ref="BROKER-001",
            evidence=self.evidence(),
        )
        second = self.boundary.record_trusted_broker_ack(
            reservation_id="RES-001",
            broker_order_ref="BROKER-001",
            evidence=self.evidence(),
        )
        self.assertEqual(first, second)

    def test_ack_does_not_create_order_without_reservation(self):
        with self.assertRaises(Exception):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-404",
                broker_order_ref="BROKER-404",
                evidence=self.evidence(),
            )

    def test_ack_cannot_cross_trader_after_reservation(self):
        self.reserve()
        self.ledger.reserve(
            reservation_id="RES-002", idempotency_key="IDEM-002",
            account_ref="OWNER-LIVE", trader_ref="TRADER-B",
            capital_usd=D("100"), risk_usd=D("0.80"), margin_usd=D("10"),
            max_account_risk_usd=D("3.20"), max_trader_risk_usd=D("1.60"),
            max_account_capital_usd=D("200"), order_ref="ORDER-002",
        )
        self.boundary.record_trusted_broker_ack(
            reservation_id="RES-001",
            broker_order_ref="BROKER-001",
            evidence=self.evidence(),
        )
        with self.assertRaises(Exception):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-002",
                broker_order_ref="BROKER-001",
                evidence=self.evidence(),
            )

    def test_non_boolean_evidence_object_is_rejected(self):
        self.reserve()
        with self.assertRaises(TypeError):
            self.boundary.record_trusted_broker_ack(
                reservation_id="RES-001",
                broker_order_ref="BROKER-001",
                evidence=True,
            )

    def test_boundary_has_no_customer_deposit_argument(self):
        self.assertNotIn("customer_deposit", self.boundary.reserve_reviewed_order.__code__.co_varnames)

    def test_ledger_event_chain_survives_boundary(self):
        self.reserve()
        self.boundary.record_trusted_broker_ack(
            reservation_id="RES-001",
            broker_order_ref="BROKER-001",
            evidence=self.evidence(),
        )
        self.assertTrue(self.ledger.verify_event_chain())


if __name__ == "__main__":
    unittest.main()
