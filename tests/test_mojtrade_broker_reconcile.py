"""C16 cross-source accounting checks; no broker or trading network access."""
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import importlib.util
import unittest

MODULE = Path(__file__).resolve().parents[1] / "trading/mojtrade_broker_reconcile.py"
spec = importlib.util.spec_from_file_location("mojtrade_broker_reconcile", MODULE)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)

DAY = "2026-11-08"
ACCOUNT = "123"
R1 = f"{1:032x}"
R2 = f"{2:032x}"
HEADER = "account,position_id,label,state,opened_utc,stop_loss,take_profit\n"
ENTRY = "123,801,MojTrade-OMEGA-X-DEMO,open,2026-11-08T08:00:00Z,1.2,1.4\n"


def report(receipts=None, truncated=False):
    if receipts is None:
        receipts = [{"request_id": R1, "state": "committed",
                     "reported_broker_position_id": "801"}]
    return {"account": ACCOUNT, "day": DAY, "broker_verified": False,
            "truncated": truncated, "receipts": receipts}


def parse(rows=ENTRY):
    return auditor.parse_broker_csv(StringIO(HEADER + rows), account=ACCOUNT, day=DAY)


class EvidenceReconciliationTests(unittest.TestCase):
    def check(self, rows=ENTRY, receipts=None, truncated=False):
        return auditor.reconcile(report(receipts, truncated), parse(rows),
                                 account=ACCOUNT, day=DAY)

    def test_matching_fill_has_consistent_data_but_never_commercial_readiness(self):
        actual = self.check()
        self.assertTrue(actual["evidence_consistent"])
        self.assertEqual(actual["matched_fills"], 1)
        self.assertEqual(actual["issues"], [])
        self.assertFalse(actual["broker_source_authenticated"])
        self.assertFalse(actual["commercial_readiness"])

    def test_broker_position_missing(self):
        result = self.check(rows="")
        self.assertFalse(result["evidence_consistent"])
        self.assertIn("position_missing_from_broker_evidence:801", result["issues"])

    def test_untracked_mojtrade_position_is_blocking(self):
        extra = "123,802,MojTrade-Demo-QuantumScalp-v2-TRADE,open,2026-11-08T08:01:00Z,1.0,1.3\n"
        result = self.check(rows=ENTRY + extra)
        self.assertIn("orphan_mojtrade_position:802", result["issues"])

    def test_unrelated_manual_position_can_coexist(self):
        manual = "123,802,MANUAL,open,2026-11-08T09:00:00Z,,\n"
        self.assertTrue(self.check(rows=ENTRY + manual)["evidence_consistent"])

    def test_missing_stop_or_take_protection_is_blocking(self):
        for stop, take in (("", "1.4"), ("1.2", ""), ("NaN", "1.4"),
                           ("-2", "1.4"), ("Infinity", "1.4")):
            row = f"123,801,MojTrade-OMEGA-X-DEMO,open,2026-11-08T08:00:00Z,{stop},{take}\n"
            with self.subTest(row=row):
                self.assertIn("protection_not_evidenced:801", self.check(rows=row)["issues"])

    def test_truncated_receipts_cannot_be_declared_consistent(self):
        self.assertIn("truncated_receipts", self.check(truncated=True)["issues"])

    def test_pending_reservation_is_unresolved(self):
        rows = [{"request_id": R1, "state": "reserved",
                 "reported_broker_position_id": None}]
        self.assertIn(f"unsettled_reservation:{R1}", self.check(rows="", receipts=rows)["issues"])

    def test_empty_receipts_is_not_evidence_of_success(self):
        result = self.check(rows="", receipts=[])
        self.assertIn("no_receipts", result["issues"])
        self.assertIn("no_committed_trade_evidence", result["issues"])

    def test_duplicate_broker_id_rejected(self):
        with self.assertRaisesRegex(auditor.EvidenceError, "duplicate_broker_position"):
            parse(ENTRY + ENTRY)

    def test_foreign_account_data_rejected(self):
        with self.assertRaisesRegex(auditor.EvidenceError, "broker_account_mismatch"):
            parse(ENTRY.replace("123,", "999,"))

    def test_wrong_or_naive_broker_date_rejected(self):
        for day in ("2026-11-07T08:00:00Z", "2026-11-08T08:00:00"):
            with self.subTest(day=day):
                with self.assertRaisesRegex(auditor.EvidenceError, "broker_day_mismatch"):
                    parse(ENTRY.replace("2026-11-08T08:00:00Z", day))

    def test_utc_normalization_accepts_same_day_timezone(self):
        row = ENTRY.replace("2026-11-08T08:00:00Z", "2026-11-08T11:30:00+03:30")
        self.assertTrue(self.check(rows=row)["evidence_consistent"])

    def test_unexpected_csv_columns_rejected(self):
        with self.assertRaisesRegex(auditor.EvidenceError, "invalid_broker_columns"):
            auditor.parse_broker_csv(StringIO("account,position_id\n123,801\n"),
                                     account=ACCOUNT, day=DAY)

    def test_invalid_or_duplicate_receipts_rejected(self):
        dup = {"request_id": R1, "state": "committed",
               "reported_broker_position_id": "801"}
        with self.assertRaisesRegex(auditor.EvidenceError, "invalid_or_duplicate_receipt"):
            self.check(receipts=[dup, dup])

    def test_uncorroborated_claims_cannot_be_labeled_broker_verified(self):
        payload = report()
        payload["broker_verified"] = True
        with self.assertRaisesRegex(auditor.EvidenceError, "invalid_receipt_report"):
            auditor.reconcile(payload, parse(), account=ACCOUNT, day=DAY)

    def test_strategy_label_mismatch_is_blocking(self):
        row = ENTRY.replace("MojTrade-OMEGA-X-DEMO", "ANOTHER-BOT")
        self.assertIn("unexpected_strategy_label:801", self.check(rows=row)["issues"])


if __name__ == "__main__":
    unittest.main()
