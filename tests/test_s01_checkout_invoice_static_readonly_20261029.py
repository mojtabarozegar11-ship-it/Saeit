"""S-01 static invoice scanner: no raw customer/source disclosure."""
import tempfile
import io
from contextlib import redirect_stdout
import unittest
from pathlib import Path

from scripts.s01_checkout_invoice_static_readonly_20261029 import (
    inspect_source, read_regular, main,
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
            self.assertFalse(result["source_contract_complete"])
            self.assertFalse(result["safe_to_publish"])
            self.assertIn("mpw_commerce/downloads.py:download_paid_item", result["missing_contract_functions"])
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

    def test_intermediate_symlink_and_parent_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "invoice.py").write_text("SECRET = 'never-read'", encoding="utf-8")
            (root / "mpw_commerce").symlink_to(outside, target_is_directory=True)
            with self.assertRaises((OSError, RuntimeError)):
                read_regular(root, "mpw_commerce/invoice.py")
            with self.assertRaises(RuntimeError):
                read_regular(root, "../outside/invoice.py")
            with self.assertRaises(RuntimeError):
                read_regular(root, "/etc/passwd")

    def test_hardlinked_regular_file_is_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "first.py").write_text("safe = True", encoding="utf-8")
            os.link(root / "first.py", root / "second.py")
            with self.assertRaises(RuntimeError):
                read_regular(root, "second.py")

    def test_missing_modules_remain_unknown_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect_source(Path(tmp), require_wsg=False)
            self.assertTrue(all(not m["exists"] for m in result["modules"]))
            self.assertFalse(result["buyer_delivery_verified"])
            self.assertFalse(result["source_contract_complete"])
            self.assertGreaterEqual(len(result["missing_contract_functions"]), 5)


    def test_placeholder_handlers_are_not_counted_as_implemented(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "mpw_commerce"
            folder.mkdir()
            (folder / "invoicing.py").write_text(
                "def reserve_order_invoice(order):\n"
                "    pass\n", encoding="utf-8"
            )
            (folder / "downloads.py").write_text(
                "def download_paid_item(request):\n"
                "    raise NotImplementedError('not ready')\n", encoding="utf-8"
            )
            (folder / "settlement.py").write_text(
                "def settle_order_invoice(order):\n"
                "    return None\n", encoding="utf-8"
            )
            (folder / "entitlements.py").write_text(
                "def can_access_purchased_digital_item(order):\n"
                "    return False\n", encoding="utf-8"
            )
            result = inspect_source(root, require_wsg=False)
            self.assertFalse(result["source_contract_complete"])
            self.assertIn("mpw_commerce/settlement.py:settle_order_invoice",
                          result["stub_contract_functions"])
            self.assertIn("mpw_commerce/entitlements.py:can_access_purchased_digital_item",
                          result["missing_contract_functions"])
            self.assertIn("mpw_commerce/invoicing.py:reserve_order_invoice",
                          result["stub_contract_functions"])
            self.assertIn("mpw_commerce/downloads.py:download_paid_item",
                          result["stub_contract_functions"])
            self.assertIn("mpw_commerce/downloads.py:download_paid_item",
                          result["missing_contract_functions"])
            self.assertFalse(result["safe_to_publish"])

    def test_dormant_nested_orm_calls_do_not_count_as_live_invoice_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "mpw_commerce"
            folder.mkdir()
            (folder / "invoicing.py").write_text(
                "def reserve_order_invoice(order):\n"
                "    def unused():\n"
                "        return Invoice.objects.get_or_create(order=order)\n"
                "    return None\n", encoding="utf-8",
            )
            (folder / "settlement.py").write_text(
                "def settle_order_invoice(order):\n"
                "    class Unused:\n"
                "        def fake(self):\n"
                "            return CommerceReceipt.objects.create(order=order)\n"
                "    return False\n", encoding="utf-8",
            )
            result = inspect_source(root, require_wsg=False)
            invoice = result["modules"][0]["functions"][0]
            settlement = next(x for x in result["modules"] if x["module"] == "mpw_commerce/settlement.py")["functions"][0]
            self.assertTrue(invoice["is_stub"])
            self.assertFalse(invoice["has_get_or_create_call"])
            self.assertTrue(settlement["is_stub"])
            self.assertFalse(settlement["has_create_call"])
            self.assertFalse(settlement["has_verified_receipt_name"])
            self.assertFalse(result["source_contract_complete"])
            self.assertFalse(result["safe_to_publish"])

    def test_nested_only_handler_is_a_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "mpw_commerce"
            folder.mkdir()
            (folder / "downloads.py").write_text(
                "def download_paid_item(request):\n"
                "    def unused():\n"
                "        return request\n", encoding="utf-8",
            )
            result = inspect_source(root, require_wsg=False)
            self.assertIn("mpw_commerce/downloads.py:download_paid_item",
                          result["stub_contract_functions"])

    def test_offline_cli_never_claims_delivery_or_prints_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mpw_commerce").mkdir()
            (root / "mpw_commerce" / "invoicing.py").write_text(
                "SECRET_TOKEN = 'synthetic-private-value'\n"
                "def reserve_order_invoice(order):\n"
                "    return order\n", encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--offline-root", str(root)])
            self.assertEqual(code, 2)
            self.assertIn('"offline_copy_only": true', output.getvalue())
            self.assertIn('"safe_to_publish": false', output.getvalue())
            self.assertNotIn("synthetic-private-value", output.getvalue())

    def test_regular_source_read_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"def checkout_invoice(request):\n    return None\n"
            (root / "source.py").write_bytes(data)
            self.assertEqual(read_regular(root, "source.py"), data)


    def test_unconditional_literal_allow_and_empty_invoice_are_not_working_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "mpw_commerce"
            folder.mkdir()
            (folder / "entitlements.py").write_text(
                "def can_access_purchased_digital_item(order):\n"
                "    return True\n", encoding="utf-8"
            )
            (folder / "invoicing.py").write_text(
                "def reserve_order_invoice(order):\n"
                "    return {}\n", encoding="utf-8"
            )
            (folder / "downloads.py").write_text(
                "def download_paid_item(request):\n"
                "    raise RuntimeError('unavailable')\n", encoding="utf-8"
            )
            result = inspect_source(root, require_wsg=False)
            self.assertFalse(result["source_contract_complete"])
            for label in (
                "mpw_commerce/entitlements.py:can_access_purchased_digital_item",
                "mpw_commerce/invoicing.py:reserve_order_invoice",
                "mpw_commerce/downloads.py:download_paid_item",
            ):
                self.assertIn(label, result["stub_contract_functions"])
                self.assertIn(label, result["missing_contract_functions"])
            self.assertFalse(result["safe_to_publish"])



if __name__ == "__main__":
    unittest.main()
