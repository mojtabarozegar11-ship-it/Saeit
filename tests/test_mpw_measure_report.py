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

    def test_no_session_identifiers_emitted_in_report(self):
        token = "f" * 32
        x = summarize([dict(site="store", session=token, page="/store/", event="engaged")], 7)
        self.assertNotIn(token, str(x))


if __name__ == "__main__":
    unittest.main()
