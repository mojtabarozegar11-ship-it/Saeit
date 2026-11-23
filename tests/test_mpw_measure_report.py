"""Static contract tests: no live web requests or fabricated customer events."""
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_measure_report import load_events, summarize


class MeasurementReportTests(unittest.TestCase):
    def test_empty_dataset_is_not_a_fake_zero_sales_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            rows, invalid = load_events(Path(temp), 7)
            result = summarize(rows, 7, invalid)
            self.assertIsNone(result["paid_orders"])
            for site in ("prop", "store"):
                self.assertEqual(result["sites"][site]["opt_in_sessions"], 0)
                self.assertIsNone(result["sites"][site]["qualified_entry_to_buy_click_rate_pct"])

    def test_unique_sessions_not_page_hits_for_dropoff(self):
        rows = [
            dict(site="prop", session="a"*32, page="/moj-prop/", event="page"),
            dict(site="prop", session="a"*32, page="/moj-prop/", event="page"),
            dict(site="prop", session="a"*32, page="/moj-prop/", event="engaged"),
            dict(site="prop", session="a"*32, page="/moj-prop/", event="buy_click"),
            dict(site="prop", session="b"*32, page="/moj-prop/", event="page"),
            dict(site="prop", session="b"*32, page="/moj-prop/", event="engaged"),
        ]
        prop = summarize(rows, 7)["sites"]["prop"]
        self.assertEqual(prop["opt_in_sessions"], 2)
        self.assertEqual(prop["qualified_entry_sessions"], 2)
        self.assertEqual(prop["buy_clicks_from_qualified_entry"], 1)
        self.assertEqual(prop["qualified_entry_dropoff_proxy_pct"], 50.0)

    def test_opt_in_written_terms_lead_is_not_a_paid_invoice(self):
        # A consented enquiry is an engagement indicator, not a payment.
        from datetime import datetime, timezone
        import json
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "2026-11-24.jsonl"
            data = {
                "site": "prop", "session": "c" * 32,
                "page": "/moj-prop/", "event": "lead_click",
            }
            path.write_text(json.dumps(data) + "\n", encoding="utf-8")
            rows, invalid = load_events(
                Path(temp), 1,
                now=datetime(2026, 11, 24, 12, tzinfo=timezone.utc),
            )
        self.assertEqual(invalid, 0)
        self.assertEqual(len(rows), 1)
        report = summarize(rows, 1)
        prop = report["sites"]["prop"]
        self.assertEqual(prop["written_terms_lead_click_sessions"], 1)
        self.assertEqual(prop["buy_click_sessions"], 0)
        self.assertEqual(prop["qualified_engaged_sessions"], 1)
        self.assertIsNone(report["paid_orders"])
        self.assertNotIn(data["session"], str(report))

    def test_no_session_identifiers_emitted_in_report(self):
        token = "f" * 32
        x = summarize([dict(site="store", session=token, page="/store/", event="engaged")], 7)
        self.assertNotIn(token, str(x))


if __name__ == "__main__":
    unittest.main()
