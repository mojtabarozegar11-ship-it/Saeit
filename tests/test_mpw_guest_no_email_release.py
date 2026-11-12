"""Safety tests for the reviewed template-only email removal release."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


RELEASE_FILE = Path(__file__).resolve().parents[1] / "scripts/mpw_guest_no_email_release.py"
GUEST_FILE = Path(__file__).resolve().parents[1] / "services/mpw_trx_guest_commerce.py"
spec = importlib.util.spec_from_file_location("no_email_release", RELEASE_FILE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def template(*, input_suffix=b' required=""', copy=True):
    return (
        b'{% csrf_token %}\n<form method="post" action="/commerce/trx-easy/start/72/">\n'
        + release.EMAIL_LABEL + b'\n'
        + b'<input id="mpw-buy-email" name="email" type="email"'
        + b' autocomplete="email" maxlength="254" placeholder="you@example.com"'
        + input_suffix + b'>\n'
        + b'<button type="submit">' + release.CTA + b'</button>\n'
        + (b'Your purchases are in this browser. ' + release.EMAIL_COPY if copy else b'')
        + b'\n</form>'
    )


class EmailFreeCheckoutReleaseTests(unittest.TestCase):
    @staticmethod
    def _live_invoice_fixture(root, start_order_code, recorder_code):
        sources = {
            "services/mpw_trx_commercial_web.py": (
                start_order_code + "\n" + recorder_code
            ),
            "services/mpw_trx_commercial_context.py": "def rights_cleared_for_sale(product):\n    return False\n",
            "mpw_commerce/buyer_orders.py": "def _eligible(product):\n    return True\n",
        }
        for rel, source in sources.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(source, encoding="utf-8")

    def test_invoice_preflight_blocks_required_email_inside_record_invoice(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n    return None\n",
                "def record_invoice(order, buyer_email):\n"
                "    if not buyer_email:\n        raise ValueError('required')\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_invoice_preflight_blocks_hidden_email_access_at_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return request.POST.get('buyer_email')\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_invoice_preflight_is_read_only_with_email_free_handler(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n    return product_id\n",
                "def record_invoice(order):\n    return order\n",
            )
            before = {
                str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob("*.py")
            }
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertEqual(report["invoice_sources_examined"], 3)
            self.assertTrue(report["invoice_handler_found"])
            after = {
                str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob("*.py")
            }
            self.assertEqual(before, after)

    def test_invoice_preflight_rejects_missing_private_code(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n    return None\n",
                "",
            )
            (root / "mpw_commerce/buyer_orders.py").unlink()
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_OR_MISSING"):
                    release.audit_invoice_email_dependencies()

    def test_removes_entire_email_field_without_rewriting_branding(self):
        source = b'<h1>Brand preserved</h1>\n' + template()
        output = release.patch_template(source)
        self.assertIn(b'<h1>Brand preserved</h1>', output)
        self.assertIn(release.CTA, output)
        self.assertIn(b'{% csrf_token %}', output)
        self.assertIn(b'/commerce/trx-easy/start/72/', output)
        self.assertNotIn(b'mpw-buy-email', output)
        self.assertNotIn(b'name="email"', output)
        self.assertNotIn(release.EMAIL_COPY, output)
        self.assertIn(b'Your purchases are in this browser.', output)

    def test_copy_can_be_absent_without_disabling_no_email_release(self):
        output = release.patch_template(template(copy=False))
        release.verify_template(output)

    def test_rejects_unknown_email_label(self):
        with self.assertRaisesRegex(RuntimeError, "EMAIL_LABEL_DRIFT"):
            release.patch_template(template().replace(b'for="mpw-buy-email"', b'for="unexpected"'))

    def test_rejects_two_email_fields(self):
        with self.assertRaisesRegex(RuntimeError, "EMAIL_LABEL_DRIFT"):
            release.patch_template(template() + release.EMAIL_LABEL)

    def test_rejects_optional_email_input_instead_of_known_required_input(self):
        with self.assertRaisesRegex(RuntimeError, "EMAIL_INPUT_DRIFT"):
            release.patch_template(template(input_suffix=b''))

    def test_rejects_unexpected_email_input_name(self):
        with self.assertRaisesRegex(RuntimeError, "EMAIL_INPUT_DRIFT"):
            release.patch_template(template().replace(b'name="email"', b'name="buyer_email"'))

    def test_rejects_field_moved_outside_expected_form(self):
        original = template()
        original = original.replace(release.EMAIL_LABEL + b'\n', release.EMAIL_LABEL + b'X' * 300 + b'\n')
        with self.assertRaisesRegex(RuntimeError, "EMAIL_FIELD_STRUCTURE_DRIFT"):
            release.patch_template(original)

    def test_rejects_duplicate_purchase_cta(self):
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_DRIFT"):
            release.patch_template(template() + release.CTA)

    def test_rejects_no_csrf_field(self):
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_DRIFT"):
            release.patch_template(template().replace(b'{% csrf_token %}', b''))

    def test_verifier_rejects_email_field_remaining(self):
        with self.assertRaisesRegex(RuntimeError, "EMAIL_FIELD_REMAINS"):
            release.verify_template(template())

    def test_source_digest_pinned_to_reviewed_implementation(self):
        content = GUEST_FILE.read_bytes()
        self.assertEqual(release.sha(content), release.APPROVED_GUEST_SHA256)
        self.assertTrue(GUEST_FILE.stat().st_size > 0)
        self.assertNotIn(b"mpw_trx_email_recovery", content)
        self.assertNotIn(b"bound_checkout", content)

    def test_plan_builds_two_exact_changes_without_touching_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            live_guest, live_template = base / "guest.py", base / "checkout.html"
            source = GUEST_FILE.read_bytes()
            live_guest.write_bytes(source)
            live_template.write_bytes(template())
            with patch.object(release, "GUEST", live_guest), patch.object(release, "TEMPLATE", live_template):
                old, new = release.plan(GUEST_FILE)
                self.assertEqual(new["guest"], old["guest"])
                self.assertNotEqual(new["template"], old["template"])
                self.assertEqual(live_template.read_bytes(), old["template"])

    def test_second_plan_is_cleanly_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            live_guest, live_template = base / "guest.py", base / "checkout.html"
            live_guest.write_bytes(GUEST_FILE.read_bytes())
            live_template.write_bytes(release.patch_template(template()))
            with patch.object(release, "GUEST", live_guest), patch.object(release, "TEMPLATE", live_template):
                old, new = release.plan(GUEST_FILE)
                self.assertIsNone(new)
                self.assertIn("template", old)

    def test_refuses_half_removed_template(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            live_guest, live_template = base / "guest.py", base / "checkout.html"
            live_guest.write_bytes(GUEST_FILE.read_bytes())
            live_template.write_bytes(template().replace(release.EMAIL_LABEL, b""))
            with patch.object(release, "GUEST", live_guest), patch.object(release, "TEMPLATE", live_template):
                with self.assertRaisesRegex(RuntimeError, "EMAIL_LABEL_DRIFT"):
                    release.plan(GUEST_FILE)


if __name__ == "__main__":
    unittest.main()
