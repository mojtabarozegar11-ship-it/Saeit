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
        b'<form method="post" action="/commerce/trx-easy/start/72/">\n{% csrf_token %}\n'
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
            "services/mpw_trx_guest_delivery.py": "def _test_fixture_marker():\n    return None\n",
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
            self.assertEqual(report["invoice_sources_examined"], 4)
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

    def test_missing_recorder_is_a_release_block_even_when_handler_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n    return product_id\n",
                "",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(
                    RuntimeError, "INVOICE_RECORDER_MISSING_OR_DUPLICATED"
                ):
                    release.audit_invoice_email_dependencies()

    def test_duplicate_recorder_in_two_sources_is_a_release_block(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n    return product_id\n",
                "def record_invoice(order):\n    return order\n",
            )
            (root / "mpw_commerce/buyer_orders.py").write_text(
                "def record_invoice(order):\n    return order\n"
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(
                    RuntimeError, "INVOICE_RECORDER_MISSING_OR_DUPLICATED"
                ):
                    release.audit_invoice_email_dependencies()

    def test_hidden_email_requirement_in_reachable_invoice_helper_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return invoice_helper(request)\n"
                "def invoice_helper(request):\n"
                "    return request.POST.get('customer_email')\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_hidden_email_constant_in_reachable_helper_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "EMAIL_PARAM = 'buyer_email'\n"
                "def _start_order(request, product_id):\n"
                "    return invoice_helper(request)\n"
                "def invoice_helper(request):\n"
                "    return request.POST.get(EMAIL_PARAM)\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_outside_invoice_recorder_must_not_be_trusted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from some_other_module import record_invoice as external_recorder\n"
                "def _start_order(request, product_id):\n"
                "    return external_recorder(request)\n",
                "",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE"):
                    release.audit_invoice_email_dependencies()

    def test_imported_allowlisted_recorder_is_audited_not_auto_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from mpw_commerce.buyer_orders import record_invoice as write_invoice\n"
                "def _start_order(request, product_id):\n"
                "    return write_invoice(product_id)\n",
                "",
            )
            (root / "mpw_commerce/buyer_orders.py").write_text(
                "def record_invoice(order):\n    return order\n"
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertEqual(report["audited_imported_recorders"], 1)
            self.assertEqual(report["invoice_sources_examined"], 4)
            self.assertTrue(report["invoice_recorder_found"])

    def test_live_imported_recorder_with_required_email_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    from services.mpw_trx_guest_delivery import record_invoice\n"
                "    return record_invoice(product_id)\n",
                "",
            )
            (root / "services/mpw_trx_guest_delivery.py").write_text(
                "def normalize_email(value):\n"
                "    return value.strip().lower()\n"
                "def record_invoice(order, buyer_email):\n"
                "    return normalize_email(buyer_email)\n"
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_live_imported_recorder_still_needs_paid_delivery_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    from services.mpw_trx_guest_delivery import record_invoice\n"
                "    return record_invoice(product_id)\n",
                "",
            )
            (root / "services/mpw_trx_guest_delivery.py").write_text(
                "def record_invoice(order):\n    return order\n"
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertEqual(report["invoice_sources_examined"], 4)
            self.assertEqual(report["audited_imported_recorders"], 1)
            self.assertEqual(report["scope"],
                             "reachable_source_indicators_only_not_live_transaction")

    def test_live_recorder_alias_import_is_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from services.mpw_trx_guest_delivery import record_invoice as save\n"
                "def _start_order(request, product_id):\n"
                "    return save(product_id)\n",
                "",
            )
            (root / "services/mpw_trx_guest_delivery.py").write_text(
                "def record_invoice(order, customer_email):\n"
                "    return customer_email\n"
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_missing_actual_live_recorder_file_blocks_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return product_id\n",
                "def record_invoice(order):\n    return order\n",
            )
            (root / "services/mpw_trx_guest_delivery.py").unlink()
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_OR_MISSING"):
                    release.audit_invoice_email_dependencies()

    def test_duplicate_invoice_recorder_in_live_module_blocks_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    from services.mpw_trx_guest_delivery import record_invoice\n"
                "    return record_invoice(product_id)\n",
                "def record_invoice(order):\n    return order\n",
            )
            (root / "services/mpw_trx_guest_delivery.py").write_text(
                "def record_invoice(order):\n    return order\n"
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(
                    RuntimeError, "INVOICE_RECORDER_MISSING_OR_DUPLICATED"
                ):
                    release.audit_invoice_email_dependencies()

    def test_handler_local_allowlisted_recorder_is_audited(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    from mpw_commerce.buyer_orders import record_invoice as save\n"
                "    return save(product_id)\n",
                "",
            )
            (root / "mpw_commerce/buyer_orders.py").write_text(
                "def record_invoice(order):\n    return order\n"
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertEqual(report["audited_imported_recorders"], 1)

    def test_imported_allowlisted_recorder_missing_from_expected_module_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from services.mpw_trx_commercial_context import record_invoice as save\n"
                "def _start_order(request, product_id):\n"
                "    return save(product_id)\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(
                    RuntimeError, "INVOICE_RECORDER_IMPLEMENTATION_MISSING"
                ):
                    release.audit_invoice_email_dependencies()

    def test_allowed_recorder_with_required_email_is_still_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from mpw_commerce.buyer_orders import record_invoice as save\n"
                "def _start_order(request, product_id):\n"
                "    return save(product_id)\n",
                "",
            )
            (root / "mpw_commerce/buyer_orders.py").write_text(
                "def record_invoice(order, buyer_email):\n"
                "    return buyer_email\n"
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_relative_recorder_import_cannot_bypass_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "from .mpw_trx_commercial_context import record_invoice as save\n"
                "def _start_order(request, product_id):\n"
                "    return save(product_id)\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(
                    RuntimeError, "INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE"
                ):
                    release.audit_invoice_email_dependencies()

    def test_inline_imported_invoice_recorder_blocks_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    from external_ledger import record_invoice as commit_sale\n"
                "    return commit_sale(product_id)\n",
                "",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE"):
                    release.audit_invoice_email_dependencies()

    def test_module_qualified_invoice_recorder_blocks_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "import external_ledger as ledger\n"
                "def _start_order(request, product_id):\n"
                "    return ledger.record_invoice(product_id)\n",
                "",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_RECORDER_OUTSIDE_AUDIT_SCOPE"):
                    release.audit_invoice_email_dependencies()

    def test_split_string_email_key_blocks_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return request.POST.get('buyer_' + 'e' + 'mail')\n",
                "",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_unrelated_joined_order_reference_remains_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return request.POST.get('order_' + 'reference')\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
                self.assertTrue(report["invoice_handler_found"])

    def test_module_dict_email_field_used_by_invoice_handler_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "INVOICE_FIELDS = {'buyer': 'customer_email'}\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(INVOICE_FIELDS['buyer'])\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_module_dict_composed_email_field_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "INVOICE_FIELDS = {'buyer': 'customer_' + 'email'}\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(INVOICE_FIELDS['buyer'])\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_module_tuple_email_field_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "FIELDS = ('order_reference', 'invoice_email')\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(FIELDS[1])\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_annotated_module_mapping_email_field_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "FIELDS: dict = {'buyer': 'email'}\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(FIELDS['buyer'])\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_unreachable_module_email_mapping_is_not_an_invoice_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "LEGACY_EMAIL_FIELDS = {'old': 'customer_email'}\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get('order_reference')\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertTrue(report["invoice_handler_found"])

    def test_non_email_module_mapping_remains_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "INVOICE_FIELDS = {'buyer': 'order_reference'}\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(INVOICE_FIELDS['buyer'])\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertTrue(report["invoice_handler_found"])

    def test_unreachable_legacy_email_helper_does_not_block_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "def _start_order(request, product_id):\n"
                "    return product_id\n"
                "def old_email_recovery(request):\n"
                "    return request.POST.get('email')\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                report = release.audit_invoice_email_dependencies()
            self.assertTrue(report["invoice_handler_found"])
            self.assertGreaterEqual(report["invoice_functions_examined"], 2)

    def test_backup_dir_rejects_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            actual = root / "real"
            actual.mkdir()
            linked = root / "linked"
            linked.symlink_to(actual, target_is_directory=True)
            target = linked / "private-backups"
            with patch.object(release, "BACKUPS", target):
                with self.assertRaisesRegex(RuntimeError, "BACKUP_ANCESTOR_SYMLINK"):
                    release._backup_dir("202611120001")
            self.assertFalse(target.exists())

    def test_private_backup_creates_owner_only_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "private-backups"
            with patch.object(release, "BACKUPS", target):
                run = release._backup_dir("202611120002")
                self.assertTrue(run.is_dir())
                self.assertEqual(run.stat().st_mode & 0o777, 0o700)

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

    def test_invoice_csrf_outside_form_is_not_a_valid_checkout(self):
        clean = release.patch_template(template())
        misplaced = b'{% csrf_token %}\n' + clean.replace(b'{% csrf_token %}\n', b'')
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(misplaced)

    def test_unrelated_form_csrf_cannot_satisfy_invoice_form(self):
        clean = release.patch_template(template())
        unrelated = (
            b'<form method="post" action="/support/">{% csrf_token %}</form>'
            + clean.replace(b'{% csrf_token %}', b'')
        )
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(unrelated)

    def test_checkout_requires_post_and_internal_invoice_start_action(self):
        clean = release.patch_template(template())
        changes = (
            clean.replace(b'method="post"', b'method="get"'),
            clean.replace(b'action="/commerce/trx-easy/start/72/"',
                          b'action="https://outside.example/start/72/"'),
            clean.replace(b'action="/commerce/trx-easy/start/72/"',
                          b'action="/support/"'),
        )
        for drifted in changes:
            with self.subTest(drifted=drifted[:120]):
                with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
                    release.verify_template(drifted)

    def test_invoice_cta_must_be_inside_its_form(self):
        clean = release.patch_template(template())
        submit = b'<button type="submit">' + release.CTA + b'</button>'
        misplaced = clean.replace(submit, b'') + submit
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(misplaced)

    def test_hidden_csrf_field_inside_invoice_form_is_accepted(self):
        clean = release.patch_template(template())
        rendered = clean.replace(
            b'{% csrf_token %}',
            b'<input type="hidden" name="csrfmiddlewaretoken" value="verified-token">'
        )
        release.verify_template(rendered)

    def test_nested_forms_are_rejected_before_release(self):
        clean = release.patch_template(template())
        nested = clean.replace(b'{% csrf_token %}',
                               b'<form method="post" action="/support/"></form>{% csrf_token %}')
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(nested)

    def test_purchase_words_in_paragraph_do_not_prove_submit(self):
        clean = release.patch_template(template())
        button = b'<button type="submit">' + release.CTA + b'</button>'
        disguised = clean.replace(button, b'<p>' + release.CTA + b'</p>')
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(disguised)

    def test_disabled_or_non_submit_button_cannot_create_invoice(self):
        clean = release.patch_template(template())
        original = b'<button type="submit">' + release.CTA + b'</button>'
        for substitute in (
            b'<button type="submit" disabled>' + release.CTA + b'</button>',
            b'<button type="button">' + release.CTA + b'</button>',
        ):
            with self.subTest(button=substitute):
                with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
                    release.verify_template(clean.replace(original, substitute))

    def test_prefix_matching_cannot_approve_broken_invoice_actions(self):
        clean = release.patch_template(template())
        base = b'/commerce/trx-easy/start/72/'
        for wrong in (
            b'/commerce/trx-easy/start/72/other/',
            b'/commerce/trx-easy/start/72/?next=/support/',
            b'/commerce/trx-easy/start/0/',
            b'/commerce/trx-easy/start/72/../support/',
            b"/commerce/trx-easy/start/not-a-product/",
        ):
            with self.subTest(action=wrong):
                with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
                    release.verify_template(clean.replace(base, wrong))

    def test_product_id_template_variable_has_exact_internal_route(self):
        clean = release.patch_template(template())
        for field in (b"id", b"pk"):
            dynamic = (b'/commerce/trx-easy/start/{{ product.' + field + b' }}/')
            release.verify_template(clean.replace(
                b'/commerce/trx-easy/start/72/', dynamic
            ))

    def test_duplicate_form_action_attributes_fail_closed(self):
        clean = release.patch_template(template())
        duplicate = clean.replace(
            b'<form method="post" action="/commerce/trx-easy/start/72/">',
            b'<form method="post" action="/commerce/trx-easy/start/72/" '
            b'action="/support/">',
        )
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(duplicate)

    def test_disabled_hidden_csrf_control_is_not_submitted(self):
        clean = release.patch_template(template())
        disabled = clean.replace(
            b'{% csrf_token %}',
            b'<input type="hidden" disabled name="csrfmiddlewaretoken" value="xyz">',
        )
        with self.assertRaisesRegex(RuntimeError, "FORM_CONTRACT_LOST"):
            release.verify_template(disabled)

    def test_enabled_input_submit_may_be_used_instead_of_button(self):
        clean = release.patch_template(template())
        old = b'<button type="submit">' + release.CTA + b'</button>'
        new = b'<input type="submit" value="' + release.CTA + b'">'
        release.verify_template(clean.replace(old, new))

    @staticmethod
    def _rendered_checkout(product_id=72):
        clean = release.patch_template(template())
        clean = clean.replace(
            b'{% csrf_token %}',
            b'<input type="hidden" name="csrfmiddlewaretoken" '
            b'value="1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01">',
        )
        if product_id != 72:
            clean = clean.replace(b'/commerce/trx-easy/start/72/',
                                  b'/commerce/trx-easy/start/' +
                                  str(product_id).encode() + b'/')
        return clean

    def test_all_three_public_rendered_form_contracts_are_valid(self):
        for product_id in (72, 225, 879):
            with self.subTest(product=product_id):
                report = release.verify_live_checkout_markup(
                    self._rendered_checkout(product_id), product_id
                )
                self.assertEqual(report["http_method"], "POST")
                self.assertTrue(report["rendered_csrf"])
                self.assertFalse(report["email_field"])

    def test_live_required_or_optional_email_fields_both_block_release(self):
        for required in (True, False):
            with self.subTest(required=required):
                html = self._rendered_checkout() + (
                    b'<input type="email" name="email"' +
                    (b' required' if required else b'') + b'>'
                )
                with self.assertRaisesRegex(RuntimeError, "LIVE_EMAIL_FIELD_PRESENT"):
                    release.verify_live_checkout_markup(html, 72)

    def test_live_atelier_missing_csrf_is_a_release_block(self):
        html = self._rendered_checkout(879)
        html = html.replace(
            b'<input type="hidden" name="csrfmiddlewaretoken" '
            b'value="1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01">',
            b'',
        )
        with self.assertRaisesRegex(RuntimeError, "LIVE_INVOICE_CONTRACT_INVALID:879"):
            release.verify_live_checkout_markup(html, 879)

    def test_live_unrendered_csrf_tag_is_not_a_real_token(self):
        original = release.patch_template(template())
        with self.assertRaisesRegex(RuntimeError, "LIVE_INVOICE_CONTRACT_INVALID:72"):
            release.verify_live_checkout_markup(original, 72)

    def test_live_wrong_product_invoice_action_blocks_release(self):
        with self.assertRaisesRegex(RuntimeError, "LIVE_INVOICE_ACTION_MISSING:225"):
            release.verify_live_checkout_markup(self._rendered_checkout(72), 225)

    def test_live_disabled_and_empty_csrf_controls_are_rejected(self):
        original = self._rendered_checkout(72)
        for changed in (
            original.replace(b'type="hidden" name="csrfmiddlewaretoken"',
                             b'type="hidden" disabled name="csrfmiddlewaretoken"'),
            original.replace(
                b'value="1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01"',
                b'value=""'
            ),
        ):
            with self.subTest(case=changed[-120:]):
                with self.assertRaisesRegex(RuntimeError, "LIVE_INVOICE_CONTRACT_INVALID:72"):
                    release.verify_live_checkout_markup(changed, 72)

    def test_live_short_csrf_control_does_not_prove_browser_security(self):
        html = self._rendered_checkout(72).replace(
            b'value="1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01"',
            b'value="short-token"'
        )
        with self.assertRaisesRegex(RuntimeError, "LIVE_INVOICE_CONTRACT_INVALID:72"):
            release.verify_live_checkout_markup(html, 72)

    def test_live_form_probe_rejects_non_allowlisted_product(self):
        with self.assertRaisesRegex(RuntimeError, "LIVE_PRODUCT_NOT_ALLOWLISTED"):
            release.verify_live_checkout_markup(self._rendered_checkout(72), 73)

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

    def test_verifier_rejects_hidden_email_aliases_and_alternate_quotes(self):
        clean = release.patch_template(template())
        variants = (
            b'<input type="hidden" name="purchase_email" value="">',
            b"<input name='buyer_email' type='hidden' value=''>",
            b'<textarea name="customer_email"></textarea>',
            b'<select name="invoice_email"><option>none</option></select>',
            b'<input name="contact" type="email">',
            b"<input type='email' name='contact'>",
            b'<input type=email name=contact>',
            b'<button name="buyer_email" type="submit">Create my TRX payment invoice</button>',
            b'<button name=contact id=email-submit type=submit>Buy</button>',
        )
        for extra in variants:
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(RuntimeError, "EMAIL_FIELD_REMAINS"):
                    release.verify_template(clean + extra)

    def test_quoted_greater_than_cannot_hide_email_field(self):
        clean = release.patch_template(template())
        for extra in (
            b'<input title="a > b" type="hidden" name="buyer_email">',
            b'<button data-note="x > y" name="email" type="submit">Continue</button>',
            b"<textarea data-example='a > b' id='customer-email'></textarea>",
        ):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(RuntimeError, "EMAIL_FIELD_REMAINS"):
                    release.verify_template(clean + extra)

    def test_quoted_greater_than_without_email_still_passes(self):
        clean = release.patch_template(template())
        release.verify_template(
            clean + b'<input title="a > b" type="hidden" name="order_ref">'
        )

    def test_verifier_blocks_email_id_and_autocomplete_alias(self):
        clean = release.patch_template(template())
        for extra in (
            b'<input name="contact" type="hidden" id="owner_email">',
            b'<input name="contact" type="text" autocomplete="email">',
            b'<textarea id="buyer_email" name="contact"></textarea>',
            b'<select id=notify_email name=contact></select>',
        ):
            with self.subTest(extra=extra):
                with self.assertRaisesRegex(RuntimeError, "EMAIL_FIELD_REMAINS"):
                    release.verify_template(clean + extra)

    def test_release_preflight_blocks_composed_email_module_constant(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "BUYER_FIELD = 'buyer_' + 'e' + 'mail'\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(BUYER_FIELD)\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_release_preflight_blocks_annotated_email_constant(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._live_invoice_fixture(
                root,
                "FIELD: str = 'contact_' + 'email'\n"
                "def _start_order(request, product_id):\n"
                "    return request.POST.get(FIELD)\n",
                "def record_invoice(order):\n    return order\n",
            )
            with patch.object(release, "APP", root):
                with self.assertRaisesRegex(RuntimeError, "INVOICE_EMAIL_DEPENDENCY"):
                    release.audit_invoice_email_dependencies()

    def test_verifier_allows_non_email_controls(self):
        clean = release.patch_template(template())
        release.verify_template(clean + (
            b'<input type="hidden" name="csrfmiddlewaretoken" value="example">'
            b'<input name="invoice_reference" type="text">'
        ))

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


    def _exercise_guarded_publish(self, public_probe, *, idempotent=False,
                                  fail_after_replace=False, concurrent_drift=False):
        """Isolated files only: never cPanel, wallet, mail, or public HTTPS."""
        import contextlib
        import io
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guest = root / "guest.py"
            checkout = root / "checkout.html"
            original = {"guest": b"original guest module",
                        "template": b"original checkout template"}
            desired = {"guest": b"replacement signed guest module",
                       "template": b"checkout template without email"}
            guest.write_bytes(desired["guest"] if idempotent else original["guest"])
            checkout.write_bytes(desired["template"] if idempotent else original["template"])
            backup = root / "private-backup"
            def private_backup(_run):
                backup.mkdir(mode=0o700)
                return backup
            restart = Mock()
            def verified_public_probe():
                if concurrent_drift:
                    checkout.write_bytes(b"third-party checkout edit")
                    raise RuntimeError("CONCURRENT_OWNER_EDIT")
                if isinstance(public_probe, Exception):
                    raise public_probe
                return public_probe
            probe = Mock(side_effect=verified_public_probe)
            original_write = release._write_atomic
            state = {"failed_once": False}
            def guarded_write(target, payload, expected_hash):
                original_write(target, payload, expected_hash)
                if (fail_after_replace and not state["failed_once"]
                        and target == checkout and payload == desired["template"]):
                    state["failed_once"] = True
                    raise RuntimeError("POST_RENAME_FSYNC_FAILURE")
            plan = Mock(return_value=(desired if idempotent else original,
                                     None if idempotent else desired))
            sink = io.StringIO()
            with patch.multiple(
                release, GUEST=guest, TEMPLATE=checkout,
                guard=lambda: None,
                audit_invoice_email_dependencies=lambda: {"invoice_handler_found": True},
                plan=plan,
                _backup_dir=private_backup,
                _restart=restart,
                _write_atomic=guarded_write,
                audit_live_public_checkout_forms=probe,
            ):
                with contextlib.redirect_stdout(sink):
                    try:
                        release.publish("202611130001", root / "source-not-used.py")
                        error = None
                    except RuntimeError as exc:
                        error = str(exc)
            return {
                "before": original, "desired": desired,
                "final": {"guest": guest.read_bytes(), "template": checkout.read_bytes()},
                "backup_exists": backup.exists(),
                "restart_count": restart.call_count,
                "probe_count": probe.call_count,
                "message": sink.getvalue(), "error": error,
            }

    def test_publish_rolls_back_every_file_when_public_checkout_fails(self):
        state = self._exercise_guarded_publish(RuntimeError("PUBLIC_GET_BLOCKED"))
        self.assertIn("PUBLIC_GET_BLOCKED", state["error"])
        self.assertEqual(state["final"], state["before"])
        self.assertEqual(state["restart_count"], 2)
        self.assertEqual(state["probe_count"], 1)
        self.assertNotIn("PUBLISHED", state["message"])
        self.assertTrue(state["backup_exists"])

    def test_publish_requires_all_three_checked_public_skus(self):
        state = self._exercise_guarded_publish([{"product_id": 72}, {"product_id": 225}])
        self.assertIn("PUBLIC_BUYER_FORMS_UNVERIFIED", state["error"])
        self.assertEqual(state["final"], state["before"])
        self.assertEqual(state["restart_count"], 2)
        self.assertNotIn("PUBLISHED", state["message"])

    def test_publish_succeeds_only_after_six_public_form_checks(self):
        proof = [{"product_id": pid, "route": path}
                 for pid, path in release.PUBLIC_CHECKOUT_ROUTES]
        state = self._exercise_guarded_publish(proof)
        self.assertIsNone(state["error"])
        self.assertEqual(state["final"], state["desired"])
        self.assertEqual(state["restart_count"], 1)
        self.assertEqual(state["probe_count"], 1)
        self.assertIn("PUBLIC_BUYER_FORMS_VERIFIED=YES", state["message"])

    def _anonymous_six_route_audit(self, *, bad_csp=False, bad_cache=False,
                                   bad_mime=False, redirect=False,
                                   email_field=False):
        """Mock actual public HTTP responses without touching the Internet."""
        from urllib.parse import urlsplit
        from unittest.mock import Mock
        class FakeResponse:
            status = 200
            def __init__(self, url, data, headers):
                self._url = url
                self._data = data
                self.headers = headers
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return self._url
            def read(self, size):
                return self._data[:size]
        seen = []
        def fake_open(request, timeout):
            url = request.full_url
            path = urlsplit(url).path
            routes = dict((route, pid) for pid, route in release.PUBLIC_CHECKOUT_ROUTES)
            self.assertIn(path, routes)
            self.assertEqual(request.get_method(), "GET")
            self.assertTrue(0 < timeout <= 12)
            seen.append(path)
            body = self._rendered_checkout(routes[path])
            if email_field:
                body += b'<input type="email" name="email" required>'
            headers = {
                "Content-Type": "application/json" if bad_mime else "text/html; charset=utf-8",
                "Content-Security-Policy":
                    ("script-src 'self'; form-action 'self'; frame-ancestors 'none'"
                     if bad_csp else
                     "default-src 'self'; script-src 'none'; form-action 'self'; frame-ancestors 'none'"),
                "Cache-Control": "private, no-cache" if bad_cache else "private, no-store",
            }
            final = url + "?redirected=1" if redirect else url
            return FakeResponse(final, body, headers)
        with patch("urllib.request.urlopen", side_effect=fake_open):
            try:
                result = release.audit_live_public_checkout_forms()
                error = None
            except RuntimeError as exc:
                result = None
                error = str(exc)
        return seen, result, error

    def test_six_real_public_checkout_paths_are_get_only_and_verified(self):
        paths, evidence, error = self._anonymous_six_route_audit()
        self.assertIsNone(error)
        self.assertEqual(len(paths), 6)
        self.assertEqual(len(evidence), 6)
        self.assertEqual(sum(x["route_group"] == "canonical" for x in evidence), 3)
        self.assertEqual(sum(x["route_group"] == "alias" for x in evidence), 3)
        self.assertEqual(sorted(x["product_id"] for x in evidence),
                         [72, 72, 225, 225, 879, 879])

    def test_six_route_public_probe_rejects_bad_script_csp(self):
        _, evidence, error = self._anonymous_six_route_audit(bad_csp=True)
        self.assertIsNone(evidence)
        self.assertIn("LIVE_CHECKOUT_CSP_UNSAFE:72", error)

    def test_six_route_public_probe_rejects_missing_no_store(self):
        _, evidence, error = self._anonymous_six_route_audit(bad_cache=True)
        self.assertIsNone(evidence)
        self.assertIn("LIVE_CHECKOUT_CACHE_UNSAFE:72", error)

    def test_six_route_public_probe_rejects_non_html(self):
        _, evidence, error = self._anonymous_six_route_audit(bad_mime=True)
        self.assertIsNone(evidence)
        self.assertIn("LIVE_CHECKOUT_WRONG_CONTENT_TYPE:72", error)

    def test_six_route_public_probe_rejects_redirects(self):
        _, evidence, error = self._anonymous_six_route_audit(redirect=True)
        self.assertIsNone(evidence)
        self.assertIn("LIVE_CHECKOUT_REDIRECT_OR_HTTP:72", error)

    def test_six_route_public_probe_rejects_customer_email_input(self):
        _, evidence, error = self._anonymous_six_route_audit(email_field=True)
        self.assertIsNone(evidence)
        self.assertIn("LIVE_EMAIL_FIELD_PRESENT:72", error)

    def test_idempotent_publish_never_skips_public_reverification(self):
        state = self._exercise_guarded_publish(RuntimeError("STALE_PUBLIC_FORM"),
                                              idempotent=True)
        self.assertIn("STALE_PUBLIC_FORM", state["error"])
        self.assertEqual(state["final"], state["desired"])
        self.assertEqual(state["restart_count"], 0)
        self.assertFalse(state["backup_exists"])
        self.assertEqual(state["probe_count"], 1)
        self.assertNotIn("ALREADY_INSTALLED", state["message"])


    def test_post_rename_fsync_failure_restores_both_owned_files(self):
        state = self._exercise_guarded_publish(
            [{"product_id": pid} for pid in release.PUBLIC_CHECKOUT_PRODUCTS],
            fail_after_replace=True,
        )
        self.assertIn("POST_RENAME_FSYNC_FAILURE", state["error"])
        self.assertEqual(state["final"], state["before"])
        self.assertEqual(state["restart_count"], 1)
        self.assertEqual(state["probe_count"], 0)
        self.assertNotIn("PUBLISHED", state["message"])

    def test_concurrent_unexpected_file_edit_never_gets_overwritten(self):
        state = self._exercise_guarded_publish(
            [{"product_id": pid} for pid in release.PUBLIC_CHECKOUT_PRODUCTS],
            concurrent_drift=True,
        )
        self.assertIn("ROLLBACK_CONFLICT:template", state["error"])
        self.assertEqual(state["final"]["guest"], state["before"]["guest"])
        self.assertEqual(state["final"]["template"], b"third-party checkout edit")
        self.assertEqual(state["restart_count"], 2)
        self.assertNotIn("PUBLISHED", state["message"])



if __name__ == "__main__":
    unittest.main()
