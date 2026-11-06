"""Current and retired checkout traffic must not be mixed in sales KPIs."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
import gzip
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import mpw_sales_intake_readonly_20261024 as intake


class StoreCheckoutFamilyTests(unittest.TestCase):
    def test_route_family_only_matches_exact_current_or_legacy_paths(self):
        self.assertEqual(intake.checkout_family("/commerce/book/72/"), "canonical_checkout")
        self.assertEqual(intake.checkout_family("/store/product/225/checkout/"), "legacy_checkout")
        for path in ("/commerce/book/0/", "/commerce/book/72/extra/",
                     "/commerce/book/72", "/store/product/225/",
                     "/store/product/72/checkout/extra/", "/commerce/trx-easy/invoice/1/"):
            self.assertIsNone(intake.checkout_family(path), path)
        # Older GitHub Actions source checks still expect this legacy label.
        self.assertEqual(intake.route_bucket("/store/product/72/checkout/"), "product_checkout")

    def test_synthetic_archive_separates_checkout_errors_without_identifiers(self):
        now = datetime(2026, 11, 6, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            (home / "logs").mkdir()
            requests = [
                ("/commerce/book/72/", 200),
                ("/commerce/book/879/", 404),
                ("/store/product/72/checkout/", 404),
                ("/store/product/225/checkout/", 503),
                ("/store/", 200),
                ("/store/product/225/", 200),
            ]
            with gzip.open(home / "logs" / "mojplaywin.com-20261105.gz", "wt", encoding="utf-8") as file:
                for path, status in requests:
                    file.write(f'203.0.113.9 - - [05/Nov/2026:12:00:00 +0000] '
                               f'"GET {path} HTTP/1.1" {status} 200 "-" "Mozilla/5.0"\n')
            stream = StringIO()
            with (patch.object(intake, "HOME", home), patch.object(intake, "NOW", now),
                  patch.object(intake, "CUTOFF", now.replace(day=1)),
                  redirect_stdout(stream)):
                intake.visitor_logs()
            printed = stream.getvalue()
            self.assertNotIn("203.0.113.9", printed)
            self.assertNotIn("Mozilla/5.0", printed)
            output = dict(line.split("=", 1) for line in printed.splitlines())
            visitors = json.loads(output["MPW_VISITOR_LOGS"])
            self.assertEqual(visitors["checkout_page_hits"], 4)
            self.assertEqual(visitors["canonical_checkout_hits"], 2)
            self.assertEqual(visitors["legacy_checkout_hits"], 2)
            self.assertEqual(visitors["store_landing_hits"], 1)
            errors = json.loads(output["MPW_ERROR_BUCKETS"])["codes_by_route"]
            self.assertEqual(errors["canonical_checkout:404"], 1)
            self.assertEqual(errors["legacy_checkout:404"], 1)
            self.assertEqual(errors["legacy_checkout:503"], 1)
            self.assertNotIn("product_checkout:404", errors)
            canon = json.loads(output["MPW_CANONICAL_SKU_CHECKOUT_BY_DAY"])["day_sku_http_status"]
            legacy = json.loads(output["MPW_LEGACY_SKU_CHECKOUT_BY_DAY"])["day_sku_http_status"]
            self.assertEqual(canon["2026-11-05:sku_72:200"], 1)
            self.assertEqual(canon["2026-11-05:sku_879:404"], 1)
            self.assertEqual(legacy["2026-11-05:sku_72:404"], 1)
            self.assertEqual(legacy["2026-11-05:sku_225:503"], 1)


if __name__ == "__main__":
    unittest.main()
