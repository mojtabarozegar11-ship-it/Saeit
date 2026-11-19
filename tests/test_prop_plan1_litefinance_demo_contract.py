"""Tests for the read-only LiteFinance demo evidence contract."""
from decimal import Decimal as D
import unittest

from prop_firm.plan1_litefinance_demo_contract import (
    DemoAccountSnapshot, DemoAdapterDisabled, DemoEvidenceRejected,
    DemoExecutionReport, LiteFinanceDemoEvidenceContract,
)


class LiteFinanceDemoContractTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.contract = LiteFinanceDemoEvidenceContract(
            expected_broker_account_ref="LF-DEMO-001",
            read_adapter_enabled=True,
        )
        self.snapshot = DemoAccountSnapshot(
            broker_account_ref="LF-DEMO-001",
            owner_account_ref="OWNER-LIVE",
            equity_usd=D("100"),
            free_margin_usd=D("95"),
            observed_at="2026-11-19T01:00:00Z",
            source="litefinance-demo-read-only",
            evidence_digest=self.digest,
        )
        self.report = DemoExecutionReport(
            broker_account_ref="LF-DEMO-001",
            broker_order_ref="BROKER-001",
            reservation_id="RES-001",
            trader_ref="TRADER-A",
            status="filled",
            observed_at="2026-11-19T01:01:00Z",
            source="litefinance-demo-read-only",
            evidence_digest=self.digest,
        )

    def test_default_contract_is_disabled(self):
        contract = LiteFinanceDemoEvidenceContract(
            expected_broker_account_ref="LF-DEMO-001"
        )
        with self.assertRaises(DemoAdapterDisabled):
            contract.validate_snapshot(self.snapshot)

    def test_valid_snapshot_is_accepted_as_evidence_only(self):
        self.assertEqual(
            self.contract.validate_snapshot(self.snapshot), self.snapshot
        )

    def test_snapshot_does_not_authorize_submission(self):
        self.contract.validate_snapshot(self.snapshot)
        with self.assertRaises(DemoAdapterDisabled):
            self.contract.submit_order(symbol="XAUUSD")

    def test_snapshot_requires_exact_type(self):
        with self.assertRaises(TypeError):
            self.contract.validate_snapshot(True)

    def test_snapshot_broker_account_must_match(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "broker_account_ref": "LF-DEMO-002"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_owner_reference_is_bounded(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "owner_account_ref": "owner with spaces"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_rejects_float_money(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "equity_usd": 100.0}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_rejects_negative_margin(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "free_margin_usd": D("-1")}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_requires_exact_source(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "source": "browser"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_requires_sha256_digest(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "evidence_digest": "not-a-digest"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_snapshot_requires_timestamp(self):
        bad = DemoAccountSnapshot(
            **{**self.snapshot.__dict__, "observed_at": " "}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_snapshot(bad)

    def test_valid_execution_report_is_accepted(self):
        self.assertEqual(
            self.contract.validate_execution_report(
                self.report,
                expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            ),
            self.report,
        )

    def test_report_requires_exact_type(self):
        with self.assertRaises(TypeError):
            self.contract.validate_execution_report(
                True,
                expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_account_must_match(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "broker_account_ref": "LF-DEMO-002"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_reservation_must_match(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "reservation_id": "RES-002"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_trader_must_match(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "trader_ref": "TRADER-B"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_status_is_bounded(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "status": "unknown"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_source_is_bounded(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "source": "customer-browser"}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_digest_is_required(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "evidence_digest": "b" * 63}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_report_timestamp_is_required(self):
        bad = DemoExecutionReport(
            **{**self.report.__dict__, "observed_at": ""}
        )
        with self.assertRaises(DemoEvidenceRejected):
            self.contract.validate_execution_report(
                bad, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            )

    def test_cancelled_report_is_bounded_valid_status(self):
        report = DemoExecutionReport(
            **{**self.report.__dict__, "status": "cancelled"}
        )
        self.assertEqual(
            self.contract.validate_execution_report(
                report, expected_reservation_id="RES-001",
                expected_trader_ref="TRADER-A",
            ),
            report,
        )

    def test_only_read_adapter_switch_is_present(self):
        self.assertTrue(hasattr(self.contract, "read_adapter_enabled"))
        self.assertFalse(hasattr(self.contract, "live_execution_enabled"))

    def test_contract_has_no_network_client(self):
        self.assertFalse(hasattr(self.contract, "session"))
        self.assertFalse(hasattr(self.contract, "http_client"))


if __name__ == "__main__":
    unittest.main()
