from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path
from scripts.mpw_measure_server_requests import parse_line, stage, summarize, discover_logs


class ServerRequestEvidenceTests(unittest.TestCase):
    def test_does_not_return_ip_user_agent_or_invoice_number(self):
        raw = '203.0.113.123 - - [21/Nov/2026:03:01:00 +0000] "GET /commerce/trx-easy/invoice/98765/?email=secret@example.com HTTP/2.0" 200 501 "-" "Mozilla/5.0 test agent"\n'
        record = parse_line(raw)
        self.assertEqual(record[1:3], ("store", "invoice_page"))
        self.assertNotIn("98765", str(record))
        self.assertNotIn("203.0.113.123", str(record))
        self.assertNotIn("secret@example.com", str(record))

    def test_unknown_path_is_never_counted(self):
        self.assertIsNone(stage("/admin/login/"))
        self.assertIsNone(stage("/mojprop-private/"))
        self.assertIsNone(stage("/commerce/trx-easy/invoice/000001/"))

    def test_successful_post_is_not_interpreted_as_verified_sale(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "access.log"
            file.write_text('127.0.0.1 - - [21/Nov/2026:03:01:00 +0000] "POST /commerce/trx-easy/start/12/ HTTP/1.1" 302 34 "-" "Mozilla/5.0"\n')
            report = summarize((file,), 7, datetime(2026,11,21,4,0,tzinfo=timezone.utc))
            self.assertEqual(report["stages"]["store/start_submission"]["post_2xx_or_3xx_requests"], 1)
            self.assertIsNone(report["verified_customer_purchases"])
            self.assertIsNone(report["click_to_buy_conversion_rate"])

    def test_future_month_archives_discovered_without_broad_glob(self):
        paths = discover_logs(datetime(2027,1,2,tzinfo=timezone.utc), 7)
        names = [p.name for p in paths]
        self.assertIn("mojplaywin.com.zomorodmelal.ir-ssl_log-Dec-2026.gz", names)
        self.assertIn("mojplaywin.com.zomorodmelal.ir-ssl_log-Jan-2027.gz", names)
        self.assertNotIn("zomorodmelal.ir-ssl_log-Jan-2027.gz", names)


    def test_only_published_legacy_checkout_skus_are_counted(self):
        for sku in (72, 225, 879):
            self.assertEqual(
                stage(f"/store/product/{sku}/checkout/"), ("store", "legacy_checkout")
            )
        for sku in (0, 1, 779, 999999998):
            self.assertIsNone(stage(f"/store/product/{sku}/checkout/"))

    def test_legacy_404_and_redirect_report_both_visible_without_customer_data(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "access.log"
            lines = [
                '203.0.113.66 - - [21/Nov/2026:03:01:00 +0000] "GET /store/product/225/checkout/?email=private@example.test HTTP/2.0" 404 42 "-" "Mozilla/5.0"\\n',
                '203.0.113.66 - - [21/Nov/2026:03:02:00 +0000] "GET /store/product/225/checkout/?token=private HTTP/2.0" 302 42 "-" "Mozilla/5.0"\\n',
                '203.0.113.66 - - [21/Nov/2026:03:03:00 +0000] "GET /store/product/999999998/checkout/ HTTP/2.0" 404 42 "-" "Mozilla/5.0"\\n',
            ]
            file.write_text("".join(lines))
            report = summarize((file,), 7, datetime(2026, 11, 21, 4, 0, tzinfo=timezone.utc))
            old = report["stages"]["store/legacy_checkout"]
            self.assertEqual(old["get_404_requests"], 1)
            self.assertEqual(old["get_30x_redirects"], 1)
            self.assertEqual(old["post_2xx_or_3xx_requests"], 0)
            self.assertNotIn("203.0.113.66", str(report))
            self.assertNotIn("private@example.test", str(report))
            self.assertNotIn("token=private", str(report))
            self.assertNotIn("999999998", str(report))
            self.assertIsNone(report["verified_customer_purchases"])

    def test_bot_categorized_separately(self):
        entry = '127.0.0.1 - - [21/Nov/2026:03:01:00 +0000] "GET /moj-prop/ HTTP/2.0" 200 50 "-" "Googlebot/2.1"\n'
        self.assertEqual(parse_line(entry)[-1], "likely_automated")


if __name__ == "__main__":
    unittest.main()
