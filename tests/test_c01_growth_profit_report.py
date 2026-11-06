"""Offline regression for C-01 financial marketing evidence; synthetic only."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "c01_growth_profit_report.py"
spec = importlib.util.spec_from_file_location("c01_growth_profit_report", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

BASE = {
    "event_id": "e1", "occurred_at": "2026-11-01T10:00:00+03:30",
    "market": "ZM_IR", "unit_id": "farm", "channel": "organic",
    "campaign_id": "crop", "event_type": "paid_order", "order_id": "ord1",
    "currency": "IRR", "amount": "1000", "quantity": "1", "evidence_ref": "receipt1",
}


def event(**kwargs):
    return dict(BASE, **kwargs)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "events.csv"

    def write(self, events):
        with self.path.open("w", encoding="utf-8", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=m.FIELDS)
            w.writeheader()
            w.writerows(events)
        return self.path

    def report(self, events):
        return m.reconcile(self.write(events), as_of="2026-11-01")

    def complete(self):
        return [
            event(event_id="v", event_type="visit", order_id="", amount="0", quantity="10", evidence_ref=""),
            event(event_id="l", event_type="lead", order_id="", amount="0", quantity="2", evidence_ref=""),
            event(event_id="p"),
            event(event_id="r", event_type="refund", amount="200", evidence_ref="refund1"),
            event(event_id="c", event_type="cogs", amount="300", evidence_ref="cogs1"),
            event(event_id="a", event_type="ad_spend", order_id="", amount="100", evidence_ref="ad1"),
            event(event_id="o", event_type="other_cost", order_id="", amount="50", evidence_ref="ops1"),
        ]

    def test_complete_cash_funnel(self):
        r = self.report(self.complete())
        g = r["groups"][0]
        self.assertEqual(g["net_receipts_recorded"], "800")
        self.assertEqual(g["gross_margin_recorded"], "500")
        self.assertEqual(g["cash_contribution_recorded"], "350")
        self.assertEqual(g["roas_recorded"], "8.0000")
        self.assertEqual(g["order_conversion_per_visit"], "0.1000")
        self.assertEqual(g["cost_per_paid_order"], "100.0000")
        self.assertIsNone(g["cac"])
        self.assertEqual(r["verification_level"], "SUPPLIED_RECORDS_ONLY_NOT_BANK_VERIFIED")

    def test_missing_costs_are_unknown_not_zero(self):
        g = self.report([event()])["groups"][0]
        self.assertIsNone(g["gross_margin_recorded"])
        self.assertIsNone(g["cash_contribution_recorded"])
        self.assertIsNone(g["ad_spend_recorded"])

    def test_zero_costs_can_be_explicitly_attested(self):
        es = [event(), event(event_id="c", event_type="cogs", amount="0"),
              event(event_id="a", event_type="ad_spend", order_id="", amount="0"),
              event(event_id="o", event_type="other_cost", order_id="", amount="0")]
        g = self.report(es)["groups"][0]
        self.assertEqual(g["cash_contribution_recorded"], "1000")
        self.assertIsNone(g["roas_recorded"])

    def test_refund_cannot_exceed_sale(self):
        es = [event(), event(event_id="r", event_type="refund", amount="1001")]
        with self.assertRaisesRegex(m.InvalidEvidence, "exceeds"):
            self.report(es)

    def test_refund_requires_matching_order(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "matching"):
            self.report([event(event_type="refund")])

    def test_duplicate_paid_order_rejected(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "duplicate paid_order"):
            self.report([event(), event(event_id="e2")])

    def test_duplicate_event_rejected(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "duplicate event_id"):
            self.report([event(), event()])

    def test_no_cross_currency_aggregation(self):
        es = [event(), event(event_id="e2", order_id="ord2", currency="USD", amount="4")]
        groups = self.report(es)["groups"]
        self.assertEqual(len(groups), 2)
        self.assertEqual({x["currency"] for x in groups}, {"USD", "IRR"})

    def test_no_cross_market_aggregation(self):
        es = [event(), event(event_id="e2", order_id="ord2", market="MPW_GLOBAL")]
        self.assertEqual(len(self.report(es)["groups"]), 2)

    def test_financial_event_needs_evidence(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "evidence_ref"):
            self.report([event(evidence_ref="")])

    def test_future_event_rejected(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "future event"):
            self.report([event(occurred_at="2026-11-02T00:00:00+03:30")])

    def test_timezone_required(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "timezone"):
            self.report([event(occurred_at="2026-11-01T10:00:00")])

    def test_pii_columns_rejected(self):
        with self.path.open("w", newline="") as fp:
            fp.write(",".join(m.FIELDS) + ",customer_email\n")
        with self.assertRaisesRegex(m.InvalidEvidence, "header"):
            m.reconcile(self.path, as_of="2026-11-01")

    def test_empty_evidence_not_zero(self):
        with self.assertRaisesRegex(m.InvalidEvidence, "no events"):
            self.report([])

    def test_symlink_input_rejected(self):
        self.write([event()])
        link = Path(self.tmp.name) / "alias.csv"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(m.InvalidEvidence, "symlink"):
            m.reconcile(link, as_of="2026-11-01")

    def test_report_has_no_receipt_or_order_ids(self):
        text = json.dumps(self.report(self.complete()))
        self.assertNotIn("receipt1", text)
        self.assertNotIn("ord1", text)

    def test_negative_or_scientific_not_allowed(self):
        for val in ["-1", "1e3", "NaN", "1,000"]:
            with self.subTest(val=val), self.assertRaisesRegex(m.InvalidEvidence, "money"):
                self.report([event(amount=val)])

    def test_malformed_csv_rejected(self):
        self.path.write_text(",".join(m.FIELDS)+"\n"+"bad,too,few\n")
        with self.assertRaises(m.InvalidEvidence):
            m.reconcile(self.path, as_of="2026-11-01")


if __name__ == "__main__":
    unittest.main()
