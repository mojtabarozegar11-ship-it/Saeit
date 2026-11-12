"""Offline contract tests for the cPanel invoice audit (no server connections)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mpw_invoice_ast",
    ROOT / "scripts/mpw_live_invoice_source_audit_readonly_20261112.py",
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class LiveInvoiceSourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        sources = {
            "services/mpw_trx_commercial_web.py":
                "from mpw_commerce.buyer_orders import record_invoice\n"
                "def _start_order(request):\n"
                "    return record_invoice(request)\n",
            "services/mpw_trx_commercial_context.py":
                "def rights_cleared_for_sale(product):\n"
                "    return True\n",
            "mpw_commerce/buyer_orders.py":
                "def record_invoice(order):\n"
                "    return order\n",
            "services/mpw_trx_guest_commerce.py":
                "def _new_user(request):\n    return object()\n"
                "def _identity(request):\n    return object()\n"
                "def patch_commercial(namespace):\n    return namespace\n",
            AUDIT.TEMPLATE:
                '<form>{% csrf_token %}<input name="mpw_guest"></form>',
        }
        for path, contents in sources.items():
            p = self.root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(contents)

    def test_clean_direct_source_does_not_prove_external_invoice(self):
        report = AUDIT.inspect(self.root)
        self.assertEqual(
            report["status"], "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED")
        self.assertFalse(report["safe_to_deploy"])
        self.assertFalse(report["external_invoice_code_proven_email_free"])
        self.assertTrue(report["files"][0]["invoice_import_calls"])

    def test_invoice_request_email_dependency_flagged(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("def _start_order(request):\n"
                     "    return request.POST['email']\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "EMAIL_REFERENCES_PRESENT")
        self.assertEqual(report["email_hit_functions"][0]["functions"],
                         ["_start_order"])

    def test_email_dependency_in_local_helper_flagged(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("def helper(request):\n"
                     "    return request.data.get('customer_email')\n"
                     "def _start_order(request):\n"
                     "    return helper(request)\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "EMAIL_REFERENCES_PRESENT")
        self.assertIn("helper", report["email_hit_functions"][0]["functions"])

    def test_missing_module_is_reported_not_skipped(self):
        (self.root / AUDIT.SOURCE_PATHS[2]).unlink()
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "SOURCE_MISSING_OR_UNREADABLE")
        self.assertEqual(len(report["source_problems"]), 1)
        self.assertFalse(report["safe_to_deploy"])

    def test_missing_start_handler_is_explicit_block(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("def other(request):\n    return 1\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "START_HANDLER_NOT_FOUND")

    def test_template_email_marker_is_reported_not_removed(self):
        p = self.root / AUDIT.TEMPLATE
        p.write_text('<input id="mpw-buy-email" name="email">'
                     '{% csrf_token %}')
        report = AUDIT.inspect(self.root)
        self.assertTrue(report["template"]["legacy_email_input_marker"])
        self.assertTrue(report["template"]["email_name_marker"])
        self.assertEqual(report["status"], "LEGACY_EMAIL_CHECKOUT_PRESENT")
        self.assertTrue(report["checkout_source_requires_email"])
        self.assertFalse(report["safe_to_deploy"])

    def test_missing_invoice_recorder_blocks(self):
        p = self.root / AUDIT.SOURCE_PATHS[2]
        p.write_text("def create_order(request):\n    return None\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "INVOICE_RECORDER_NOT_FOUND")
        self.assertFalse(report["invoice_recorder_found"])
        self.assertFalse(report["safe_to_deploy"])

    def test_missing_csrf_template_marker_blocks(self):
        p = self.root / AUDIT.TEMPLATE
        p.write_text('<form method="post"><input name="anonymous"></form>')
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "CHECKOUT_CSRF_MARKER_MISSING")
        self.assertFalse(report["csrf_template_marker_found"])
        self.assertFalse(report["safe_to_deploy"])

    def test_email_only_marker_blocks(self):
        p = self.root / AUDIT.TEMPLATE
        p.write_text('<form><input name="email">{% csrf_token %}</form>')
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "LEGACY_EMAIL_CHECKOUT_PRESENT")
        self.assertTrue(report["checkout_source_requires_email"])

    def test_symlinked_source_is_rejected(self):
        p = self.root / AUDIT.SOURCE_PATHS[2]
        p.unlink()
        p.symlink_to(self.root / AUDIT.SOURCE_PATHS[0])
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "SOURCE_MISSING_OR_UNREADABLE")
        self.assertEqual(report["source_problems"][0]["reason"], "ValueError")

    def test_email_type_and_aliased_hidden_controls_block(self):
        for control in (
            '<input type="email" name="contact">',
            '<input type="hidden" name="buyer_email">',
            "<textarea id='notification_email'></textarea>",
            '<select autocomplete="email" name="contact"></select>',
            '<input name=customer_email type=hidden>',
            '<button name="buyer_email" type="submit">Buy</button>',
            '<button type="submit" id="contact-email">Buy</button>',
        ):
            with self.subTest(control=control):
                p = self.root / AUDIT.TEMPLATE
                p.write_text("<form>{% csrf_token %}" + control + "</form>")
                report = AUDIT.inspect(self.root)
                self.assertTrue(report["template"]["email_control_marker"])
                self.assertEqual(report["status"], "LEGACY_EMAIL_CHECKOUT_PRESENT")

    def test_constructed_email_key_in_start_handler_blocks(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("def _start_order(request):\n"
                     "    return request.POST.get('buyer_' + 'e' + 'mail')\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "EMAIL_REFERENCES_PRESENT")
        self.assertIn("_start_order", report["email_hit_functions"][0]["functions"])

    def test_module_level_constant_alias_email_blocks(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("BUYER_FIELD = 'buyer_' + 'email'\n"
                     "def _start_order(request):\n"
                     "    return request.POST.get(BUYER_FIELD)\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "EMAIL_REFERENCES_PRESENT")

    def test_unrelated_field_does_not_trigger_email_false_positive(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("PRODUCT_FIELD = 'order_' + 'reference'\n"
                     "def _start_order(request):\n"
                     "    return request.POST.get(PRODUCT_FIELD)\n")
        p = self.root / AUDIT.TEMPLATE
        p.write_text('<form>{% csrf_token %}<input name="order_reference"></form>')
        report = AUDIT.inspect(self.root)
        self.assertEqual(
            report["status"], "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED"
        )

    def test_source_content_not_printed_or_returned(self):
        p = self.root / AUDIT.SOURCE_PATHS[0]
        p.write_text("def _start_order(request):\n"
                     "    api_token='SECRET_PRODUCTION_DO_NOT_PRINT'\n"
                     "    return api_token\n")
        report = AUDIT.inspect(self.root)
        self.assertNotIn("SECRET_PRODUCTION_DO_NOT_PRINT", repr(report))
        self.assertFalse(report["real_invoice_post_tested"])
        self.assertFalse(report["paid_receipt_download_tested"])


if __name__ == "__main__":
    unittest.main()
