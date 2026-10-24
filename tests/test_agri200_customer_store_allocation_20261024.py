"""Verify 200 uniquely allocated PRIVATE paid catalog candidates."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "agri200_customer_store_allocation",
    ROOT / "scripts/agri200_customer_store_allocation_20261024.py",
)
allocation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(allocation)


class CustomerStoreSplitTests(unittest.TestCase):
    def test_exact_split_unique_topics_and_currencies(self):
        manifest = allocation.build_allocation(ROOT / "docs/agri200_p0_catalog.tsv")
        entries = manifest["products"]
        self.assertEqual(len(entries), 200)
        self.assertEqual(len({x["product_id"] for x in entries}), 200)
        self.assertEqual(len({x["title"] for x in entries}), 200)
        self.assertEqual(manifest["customer_purchasable_count"], 0)
        self.assertEqual(entries[0]["product_id"], "AGRI-001")
        self.assertEqual(entries[99]["product_id"], "AGRI-100")
        self.assertEqual(entries[100]["product_id"], "AGRI-101")
        self.assertEqual(entries[-1]["product_id"], "AGRI-200")
        for idx, item in enumerate(entries):
            if idx < 100:
                self.assertEqual((item["locale"], item["storefront"], item["currency"]),
                                 ("en-US", "mojplaywin.com", "USD"))
                self.assertEqual(item["title"], item["catalog_title_en"])
            else:
                self.assertEqual((item["locale"], item["storefront"], item["currency"]),
                                 ("fa-IR", "zomorodmelal.ir", "IRR"))
                self.assertEqual(item["title"], item["catalog_title_fa"])

    def test_no_paper_titles_become_fake_saleable_products(self):
        entries = allocation.build_allocation(ROOT / "docs/agri200_p0_catalog.tsv")["products"]
        for item in entries:
            self.assertIsNone(item["price_minor_units"])
            for field in ("qc1000_approved", "owner_rework_cleared",
                          "rights_verified", "download_after_payment_verified",
                          "sales_enabled", "public_listing_enabled"):
                self.assertIs(item[field], False)
            self.assertTrue(item["publication_state"].startswith("PRIVATE_"))

    def test_catalog_missing_rows_fails_closed(self):
        original = (ROOT / "docs/agri200_p0_catalog.tsv").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "catalog.tsv"
            target.write_text("\n".join(original.splitlines()[:-1]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "EXACTLY_200"):
                allocation.build_allocation(target)

    def test_duplicate_titles_fail_closed(self):
        original = (ROOT / "docs/agri200_p0_catalog.tsv").read_text(encoding="utf-8")
        lines = original.splitlines()
        rows = [i for i, x in enumerate(lines) if x.startswith("AGRI-")]
        a = lines[rows[0]].split("|")
        b = lines[rows[1]].split("|")
        b[2] = a[2]
        lines[rows[1]] = "|".join(b)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "catalog.tsv"
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "REPEATED_ENGLISH"):
                allocation.build_allocation(target)


if __name__ == "__main__":
    unittest.main()
