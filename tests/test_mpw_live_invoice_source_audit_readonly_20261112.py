"""Offline contract tests for the cPanel invoice audit (no server connections)."""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
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
                (ROOT / "services/mpw_trx_guest_commerce.py").read_text(encoding="utf-8"),
            "services/mpw_trx_guest_delivery.py":
                "def delivery_helper(order):\n    return order\n",
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

    def test_quoted_angle_brackets_do_not_mask_email_controls(self):
        for control in (
            '<input data-hint="enter > then continue" name="buyer_email" type="hidden">',
            "<textarea title='a > b' id='customer-email'></textarea>",
            '<button data-note="x > y" name="email" type="submit">Buy</button>',
        ):
            with self.subTest(control=control):
                p = self.root / AUDIT.TEMPLATE
                p.write_text("<form>{% csrf_token %}" + control + "</form>")
                report = AUDIT.inspect(self.root)
                self.assertEqual(report["status"], "LEGACY_EMAIL_CHECKOUT_PRESENT")
                self.assertTrue(report["template"]["email_control_marker"])

    def test_quoted_angle_bracket_non_email_control_is_allowed(self):
        p = self.root / AUDIT.TEMPLATE
        p.write_text(
            '<form>{% csrf_token %}<input title="a > b" name="order_ref"></form>'
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(
            report["status"], "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED"
        )

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

    def _remote_gate_result(self, report):
        remote = AUDIT.REPORT_PREFIX + json.dumps(report)
        printed = io.StringIO()
        with redirect_stdout(printed):
            code = AUDIT.validate_remote_report(remote)
        return code, printed.getvalue()

    def test_remote_report_blocks_legacy_checkout_instead_of_green(self):
        p = self.root / AUDIT.TEMPLATE
        p.write_text('<input name="buyer_email">{% csrf_token %}')
        code, printed = self._remote_gate_result(AUDIT.inspect(self.root))
        self.assertEqual(code, 21)
        self.assertIn("BLOCKED_LEGACY_EMAIL_CHECKOUT_PRESENT", printed)
        self.assertNotIn("SAFE_TO_DEPLOY", printed)

    def test_remote_report_clean_snapshot_still_does_not_prove_sale(self):
        code, printed = self._remote_gate_result(AUDIT.inspect(self.root))
        self.assertEqual(code, 22)
        self.assertIn("UNVERIFIED_EXTERNAL_HELPERS_AND_PAID_RECEIPT", printed)

    def test_malformed_or_duplicate_remote_report_is_a_failure(self):
        for report in (
            "",
            "MPW_LIVE_INVOICE_SOURCE_AUDIT={broken}",
            "MPW_LIVE_INVOICE_SOURCE_AUDIT={}",
            AUDIT.REPORT_PREFIX + '{"mode":"wrong","status":"READY"}',
            (AUDIT.REPORT_PREFIX + json.dumps(AUDIT.inspect(self.root)) + "\n"
             + AUDIT.REPORT_PREFIX + json.dumps(AUDIT.inspect(self.root))),
        ):
            with self.subTest(report=report[:100]):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = AUDIT.validate_remote_report(report)
                self.assertNotEqual(code, 0)
                self.assertIn("BLOCKED_", buf.getvalue())

    def test_recorder_in_commercial_web_is_accepted_as_source_evidence(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text("def record_invoice(order):\n    return order\n"
                       "def _start_order(request):\n    return record_invoice(request)\n")
        buyer = self.root / AUDIT.SOURCE_PATHS[2]
        buyer.write_text("def _eligible(product):\n    return True\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["invoice_recorder_definition_count"], 1)
        self.assertTrue(report["invoice_recorder_found"])
        self.assertEqual(
            report["status"], "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED"
        )

    def test_live_delivery_recorder_email_requirement_blocks_source_gate(self):
        (self.root / AUDIT.SOURCE_PATHS[2]).write_text(
            "def _eligible(product):\n    return True\n"
        )
        (self.root / AUDIT.SOURCE_PATHS[4]).write_text(
            "def record_invoice(order, buyer_email):\n"
            "    if not buyer_email:\n"
            "        raise ValueError('email required')\n"
            "    return order\n"
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "EMAIL_REFERENCES_PRESENT")
        self.assertEqual(report["invoice_recorder_definition_count"], 1)
        self.assertTrue(any(
            item["file"] == AUDIT.SOURCE_PATHS[4] and
            "record_invoice" in item["functions"]
            for item in report["email_hit_functions"]
        ))
        code, printed = self._remote_gate_result(report)
        self.assertEqual(code, 21)
        self.assertIn("MPW_SOURCE_GATE=BLOCKED_EMAIL_REFERENCES_PRESENT", printed)

    def test_live_delivery_recorder_still_needs_commercial_proof(self):
        (self.root / AUDIT.SOURCE_PATHS[2]).write_text(
            "def _eligible(product):\n    return True\n"
        )
        (self.root / AUDIT.SOURCE_PATHS[4]).write_text(
            "def record_invoice(order):\n    return order\n"
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["invoice_recorder_definition_count"], 1)
        self.assertEqual(report["status"], "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED")
        self.assertFalse(report["safe_to_deploy"])

    def test_external_imported_invoice_recorder_is_unverified_not_missing(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text(
            "from services.invoice_ledger import record_invoice\n"
            "def _start_order(request):\n"
            "    return record_invoice(request)\n"
        )
        (self.root / AUDIT.SOURCE_PATHS[2]).write_text(
            "def _eligible(product):\n    return True\n"
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "INVOICE_RECORDER_EXTERNAL_UNVERIFIED")
        self.assertTrue(report["invoice_recorder_external_unverified"])
        code, printed = self._remote_gate_result(report)
        self.assertEqual(code, 21)
        self.assertIn("BLOCKED_INVOICE_RECORDER_EXTERNAL_UNVERIFIED", printed)
        evidence = json.loads(next(
            line.split("=", 1)[1] for line in printed.splitlines()
            if line.startswith("MPW_SOURCE_EVIDENCE=")
        ))
        web_entry = next(f for f in evidence["modules"]
                         if f["file"] == AUDIT.SOURCE_PATHS[0])
        self.assertIn("services.invoice_ledger.record_invoice",
                      web_entry["invoice_imports"])

    def test_handler_local_invoice_recorder_import_is_reported(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text(
            "def _start_order(request):\n"
            "    from services.mpw_invoice_ledger import record_invoice as persist\n"
            "    return persist(request)\n"
        )
        (self.root / AUDIT.SOURCE_PATHS[2]).write_text(
            "def _eligible(product):\n    return True\n"
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "INVOICE_RECORDER_EXTERNAL_UNVERIFIED")
        code, printed = self._remote_gate_result(report)
        self.assertEqual(code, 21)
        info = json.loads(next(line.split("=", 1)[1]
                               for line in printed.splitlines()
                               if line.startswith("MPW_SOURCE_EVIDENCE=")))
        web_info = next(x for x in info["modules"]
                        if x["file"] == AUDIT.SOURCE_PATHS[0])
        self.assertIn("services.mpw_invoice_ledger.record_invoice",
                      web_info["invoice_imports"])

    def test_distinct_module_invoice_recorders_are_ambiguous(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text("def record_invoice(order):\n    return order\n"
                       "def _start_order(request):\n    return record_invoice(request)\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "INVOICE_RECORDER_DUPLICATED")
        self.assertEqual(report["invoice_recorder_definition_count"], 2)
        self.assertFalse(report["invoice_recorder_found"])

    def test_duplicate_same_module_functions_are_never_silently_overwritten(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text("def _start_order(request):\n    return 1\n"
                       "def _start_order(request):\n    return 2\n")
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "DUPLICATE_SOURCE_FUNCTIONS")
        self.assertIn("_start_order", report["files"][0]["duplicate_functions"])

    def test_reviewed_guest_synthetic_email_schema_is_not_buyer_capture(self):
        report = AUDIT.inspect(self.root)
        self.assertTrue(report["guest_source_matches_reviewed_digest"])
        self.assertEqual(report["status"],
                         "DIRECT_SOURCE_CLEAN_EXTERNAL_HELPERS_UNVERIFIED")
        self.assertEqual(report["email_hit_functions"], [])
        self.assertIn("_new_user",
                      report["guest_internal_email_indicators_review_required"])

    def test_unreviewed_guest_email_lookups_block_even_if_invoice_code_clean(self):
        guest = self.root / AUDIT.SOURCE_PATHS[3]
        guest.write_text(
            "def _new_user(request):\n"
            "    return request.POST.get('email')\n"
            "def _identity(request):\n    return None\n"
            "def patch_commercial(namespace):\n    return namespace\n"
        )
        report = AUDIT.inspect(self.root)
        self.assertEqual(report["status"], "UNREVIEWED_GUEST_SOURCE")
        self.assertFalse(report["guest_source_matches_reviewed_digest"])
        self.assertFalse(report["safe_to_deploy"])

    def test_a_truncated_helper_graph_never_returns_clean(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        source = "def _start_order(request):\n    return helper0(request)\n"
        for i in range(AUDIT.MAX_HELPERS + 1):
            next_call = (f"helper{i + 1}(request)"
                         if i < AUDIT.MAX_HELPERS else "request")
            source += f"def helper{i}(request):\n    return {next_call}\n"
        web.write_text(source)
        report = AUDIT.inspect(self.root)
        self.assertTrue(report["files"][0]["helper_limit_hit"])
        self.assertEqual(report["status"], "SOURCE_HELPER_GRAPH_TRUNCATED")

    def test_nested_symlink_ancestor_must_not_expose_template(self):
        original_dir = self.root / "mpw_commerce"
        external_dir = self.root / "outside_public"
        external_dir.mkdir()
        # Move existing directory to a sibling and reintroduce a symlink in
        # the first template-path ancestor, not the final two path components.
        original_dir.rename(external_dir / "source_tree")
        original_dir.symlink_to(external_dir / "source_tree", target_is_directory=True)
        report = AUDIT.inspect(self.root)
        self.assertFalse(report["template"]["exists"])
        self.assertEqual(report["template"]["reason"], "ValueError")
        self.assertEqual(report["status"], "SOURCE_MISSING_OR_UNREADABLE")

    def test_source_gate_checks_are_present_in_manual_workflow(self):
        yml = (ROOT / ".github/workflows/"
               "mpw-live-invoice-source-audit-readonly-20261112.yml").read_text()
        self.assertIn("mpw_live_invoice_source_audit_readonly_20261112.py --validate-report", yml)
        self.assertIn("workflow_dispatch:", yml)
        self.assertNotIn("MPW_LIVE_SOURCE_AUDIT=TRANSPORT_VERIFIED", yml)
        self.assertNotIn('if [ -z "$VPS_KEY" ] || [ -z "$HOST_KEY" ]', yml)
        self.assertLess(yml.index("mode=relay"),
                        yml.index('if [ -z "$VPS_KEY" ]'))
        self.assertLess(yml.index('if [ -z "$HOST_KEY" ]'),
                        yml.index("mode=direct"))

    def test_remote_diagnostic_prints_bounded_call_names_only(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text(
            "def _start_order(request):\n"
            "    return reserve_commercial_intent(request)\n"
            "def reserve_commercial_intent(request):\n"
            "    return request.POST.get('order_reference')\n"
        )
        report = AUDIT.inspect(self.root)
        code, printed = self._remote_gate_result(report)
        self.assertEqual(code, 22)
        self.assertIn("MPW_SOURCE_GATE=UNVERIFIED_EXTERNAL_HELPERS_AND_PAID_RECEIPT", printed)
        summary = next(line.split("=", 1)[1] for line in printed.splitlines()
                       if line.startswith("MPW_SOURCE_EVIDENCE="))
        parsed = json.loads(summary)
        web_files = [f for f in parsed["modules"] if f["file"] == AUDIT.SOURCE_PATHS[0]]
        self.assertEqual(len(web_files), 1)
        self.assertIn("reserve_commercial_intent", web_files[0]["checkout_calls"])
        self.assertFalse(parsed["paid_order_verified"])
        self.assertFalse(parsed["production_changed"])

    def test_diagnostic_does_not_echo_string_literals_or_email_values(self):
        web = self.root / AUDIT.SOURCE_PATHS[0]
        web.write_text(
            "def _start_order(request):\n"
            "    secret = 'SECRET_SAMPLE_DO_NOT_LOG'\n"
            "    return secret\n"
        )
        _code, printed = self._remote_gate_result(AUDIT.inspect(self.root))
        self.assertNotIn("SECRET_SAMPLE_DO_NOT_LOG", printed)
        self.assertIn("MPW_SOURCE_EVIDENCE=", printed)
        self.assertNotIn("SAFE_TO_DEPLOY", printed)

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
