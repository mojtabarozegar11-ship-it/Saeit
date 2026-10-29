"""S-01 static invoice scanner: no raw customer/source disclosure."""
import tempfile
import unittest
from pathlib import Path

from scripts.s01_checkout_invoice_static_readonly_20261029 import (
    inspect_source, read_regular,
)


class InvoiceStaticReadOnlyTests(unittest.TestCase):
    def test_bounded_static_scan_and_idempotency_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "mpw_commerce"
            folder.mkdir()
            (folder / "invoicing.py").write_text(
                "SECRET_KEY = 'never-log-this-secret'\n"
                "def reserve_order_invoice(order):\n"
                "    return Invoice.objects.get_or_create(order=order)\n",
                encoding="utf-8",
            )
            result = inspect_source(root, require_wsg=False)
            self.assertFalse(result["invoice_idempotency_verified"])
            self.assertFalse(result["database_identity_verified"])
            self.assertEqual(result["orders_created"], 0)
            item = result["modules"][0]
            self.assertTrue(item["exists"])
            self.assertEqual(item["functions"][0]["name"], "reserve_order_invoice")
            self.assertTrue(item["functions"][0]["has_get_or_create_call"])
            self.assertNotIn("never-log-this-secret", str(result))
            self.assertNotIn("SECRET_KEY", str(result))

    def test_symlink_and_oversized_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "actual.py").write_text("x = 1", encoding="utf-8")
            (root / "alias.py").symlink_to(root / "actual.py")
            with self.assertRaises(RuntimeError):
                read_regular(root, "alias.py")
            (root / "huge.py").write_bytes(b"x" * 200001)
            with self.assertRaises(RuntimeError):
                read_regular(root, "huge.py")

    def test_missing_modules_remain_unknown_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_source(Path(tmp), require_wsg=False)
            self.assertTrue(all(not m["exists"] for m in result["modules"]))
            self.assertFalse(result["buyer_delivery_verified"])


if __name__ == "__main__":
    unittest.main()
