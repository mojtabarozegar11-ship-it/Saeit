"""Tests for pure LiteFinance demo reconciliation."""
from decimal import Decimal as D
import unittest

from prop_firm.plan1_litefinance_demo_contract import (
    DemoAccountSnapshot, DemoExecutionReport,
    LiteFinanceDemoEvidenceContract,
)
from prop_firm.plan1_demo_reconciliation import LiteFinanceDemoReconciler


class DemoReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.contract = LiteFinanceDemoEvidenceContract(
            expected_broker_account_ref="LF-DEMO-001",
            read_adapter_enabled=True,
        )
        self.reconciler = LiteFinanceDemoReconciler(self.contract)
        self.snapshot = DemoAccountSnapshot(
            broker_account_ref="LF-DEMO-001",
            owner_account_ref="OWNER-LIVE",
            equity_usd=D("100"),
            free_margin_usd=D("95"),
            observed_at="2026-11-19T02:00:00Z",
            source="litefinance-demo-read-only",
            evidence_digest=self.digest,
        )
        self.report = DemoExecutionReport(
            broker_account_ref="LF-DEMO-001",
            broker_order_ref="BROKER-001",
            reservation_id="RES-001",
            trader_ref="TRADER-A",
            status="filled",
            observed_at="2026-11-19T02:01:00Z",
            source="litefinance-demo-read-only",
            evidence_digest=self.digest,
        )

    def reconcile(self, reports=(None,), mapping=None):
        if reports == (None,):
            reports = (self.report,)
        if mapping is None:
            mapping = {"RES-001": "TRADER-A"}
        return self.reconciler.reconcile(
            snapshot=self.snapshot,
            reports=reports,
            reservation_to_trader=mapping,
        )

    def test_valid_single_report_is_verified(self):
        result = self.reconcile()
        self.assertTrue(result.verified)
        self.assertEqual(result.report_count, 1)
        self.assertEqual(result.verified_order_refs, ("BROKER-001",))

    def test_empty_report_batch_is_valid_snapshot_reconciliation(self):
        result = self.reconcile(reports=())
        self.assertTrue(result.verified)
        self.assertEqual(result.report_count, 0)

    def test_cancelled_order_is_separated(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "status": "cancelled"}
        )
        result = self.reconcile(reports=(report,))
        self.assertTrue(result.verified)
        self.assertEqual(result.cancelled_order_refs, ("BROKER-001",))
        self.assertEqual(result.verified_order_refs, ())

    def test_duplicate_broker_order_is_rejected(self):
        result = self.reconcile(reports=(self.report, self.report))
        self.assertFalse(result.verified)
        self.assertIn("duplicate_broker_order_reference", result.reasons)

    def test_duplicate_reservation_is_rejected(self):
        second = DemoExecutionReport(
            **{**self.report.__dict__, "broker_order_ref": "BROKER-002"}
        )
        result = self.reconcile(reports=(self.report, second))
        self.assertFalse(result.verified)
        self.assertIn("duplicate_reservation_reference", result.reasons)

    def test_unknown_reservation_is_rejected(self):
        result = self.reconcile(mapping={})
        self.assertFalse(result.verified)
        self.assertIn("reservation_not_in_server_map", result.reasons)

    def test_cross_trader_mapping_is_rejected(self):
        result = self.reconcile(mapping={"RES-001": "TRADER-B"})
        self.assertFalse(result.verified)
        self.assertIn("DemoEvidenceRejected", result.reasons)

    def test_wrong_broker_account_is_rejected(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "broker_account_ref": "LF-DEMO-002"}
        )
        result = self.reconcile(reports=(report,))
        self.assertFalse(result.verified)
        self.assertIn("DemoEvidenceRejected", result.reasons)

    def test_invalid_status_is_rejected(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "status": "unknown"}
        )
        result = self.reconcile(reports=(report,))
        self.assertFalse(result.verified)

    def test_invalid_source_is_rejected(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "source": "browser"}
        )
        result = self.reconcile(reports=(report,))
        self.assertFalse(result.verified)

    def test_invalid_digest_is_rejected(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "evidence_digest": "bad"}
        )
        result = self.reconcile(reports=(report,))
        self.assertFalse(result.verified)

    def test_snapshot_contract_is_reused(self):
        snapshot = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "evidence_digest": "bad"}
        )
        result = self.reconciler.reconcile(
            snapshot=snapshot, reports=(), reservation_to_trader={}
        )
        self.assertFalse(result.verified) if False else self.assertRaises(
            Exception,
            self.reconciler.reconcile,
            snapshot=snapshot, reports=(), reservation_to_trader={},
        )

    def test_reports_must_be_tuple(self):
        with self.assertRaises(TypeError):
            self.reconciler.reconcile(
                snapshot=self.snapshot, reports=[self.report],
                reservation_to_trader={"RES-001": "TRADER-A"},
            )

    def test_mapping_must_be_server_dict(self):
        with self.assertRaises(TypeError):
            self.reconciler.reconcile(
                snapshot=self.snapshot, reports=(self.report,),
                reservation_to_trader=(("RES-001", "TRADER-A"),),
            )

    def test_report_batch_is_bounded(self):
        reports = tuple(self.report for _ in range(10001))
        with self.assertRaises(TypeError):
            self.reconciler.reconcile(
                snapshot=self.snapshot, reports=reports,
                reservation_to_trader={"RES-001": "TRADER-A"},
            )

    def test_result_is_immutable(self):
        result = self.reconcile()
        with self.assertRaises(Exception):
            result.verified = False

    def test_result_contains_no_execution_permission(self):
        result = self.reconcile()
        self.assertFalse(hasattr(result, "submit"))
        self.assertFalse(hasattr(result, "live_permission"))

    def test_result_does_not_mutate_mapping(self):
        mapping = {"RES-001": "TRADER-A"}
        self.reconcile(mapping=mapping)
        self.assertEqual(mapping, {"RES-001": "TRADER-A"})

    def test_result_does_not_mutate_reports(self):
        reports = (self.report,)
        self.reconciler.reconcile(
            snapshot=self.snapshot, reports=reports,
            reservation_to_trader={"RES-001": "TRADER-A"},
        )
        self.assertEqual(reports, (self.report,))

    def test_report_count_is_exact(self):
        second = DemoExecutionReport(
            **{**self.report.__dict__,
               "broker_order_ref": "BROKER-002",
               "reservation_id": "RES-002",
               "trader_ref": "TRADER-B"}
        )
        result = self.reconcile(
            reports=(self.report, second),
            mapping={"RES-001": "TRADER-A", "RES-002": "TRADER-B"},
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.report_count, 2)

    def test_reconciler_has_no_broker_client(self):
        self.assertFalse(hasattr(self.reconciler, "session"))
        self.assertFalse(hasattr(self.reconciler, "http_client"))


if __name__ == "__main__":
    unittest.main()
