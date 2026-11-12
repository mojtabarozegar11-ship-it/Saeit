"""Offline contract tests for the read-only public checkout audit."""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mpw_form_audit", ROOT / "scripts/mpw_three_sku_public_form_evidence_20261112.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FormAuditTests(unittest.TestCase):
    def test_required_legacy_email_blocks(self):
        html = ('<form action="/commerce/trx-easy/start/72/" method="post">'
                '<label>Email address for your order</label>'
                '<input type="email" name="email" required>'
                '<button type="submit">Create my TRX payment invoice</button></form>')
        result = AUDIT.parse_checkout(html)
        self.assertEqual(result["form_count"], 1)
        self.assertEqual(result["named_email_inputs"], 1)
        self.assertEqual(result["required_email_inputs"], 1)
        self.assertTrue(result["email_label_present"])
        self.assertTrue(result["trx_invoice_cta_present"])

    def test_hidden_and_aliased_email_controls_are_detected(self):
        for markup in (
            '<input type="hidden" name="buyer_email">',
            '<input type="text" name="purchase_email" required>',
            '<input type=email name=contact>',
            '<textarea name="customer_email"></textarea>',
        ):
            with self.subTest(markup=markup):
                result = AUDIT.parse_checkout('<form>'+markup+'</form>')
                self.assertEqual(result["named_email_inputs"], 1)

    def test_email_named_submit_button_never_passes_form_gate(self):
        csrf = ('<input type="hidden" name="csrfmiddlewaretoken" value="'
                + 'a' * 64 + '">')
        for submit in (
            '<button type="submit" name="email">Create my TRX payment invoice</button>',
            '<button type="submit" name="buyer_email" value="">Create my TRX payment invoice</button>',
            '<button type="submit" id="email-alias">Create my TRX payment invoice</button>',
            '<input type="submit" name="buyer_email" value="Create my TRX payment invoice">',
        ):
            with self.subTest(submit=submit):
                html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                        + csrf + submit + '</form>')
                report = AUDIT.parse_checkout(html, 72)
                self.assertEqual(report["named_email_inputs"], 1)
                self.assertFalse(report["checkout_post_csrf_cta_valid"])

    def test_valid_no_email_form(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">'
                '<button type="submit">Create my TRX payment invoice</button></form>')
        result = AUDIT.parse_checkout(html, 72)
        self.assertEqual(result["form_count"], 1)
        self.assertEqual(result["named_email_inputs"], 0)
        self.assertFalse(result["email_label_present"])
        self.assertTrue(result["trx_invoice_cta_present"])
        self.assertTrue(result["checkout_post_csrf_cta_valid"])

    def test_cta_in_unrelated_form_cannot_pass(self):
        csrf = '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">' 
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">' + csrf + '</form>'
                '<form method="post"><button type="submit">Create my TRX payment invoice</button></form>')
        self.assertFalse(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def test_wrong_sku_get_and_missing_csrf_are_rejected(self):
        csrf = '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">'
        button = '<button type="submit">Create my TRX payment invoice</button>'
        for method, action, token in (
            ("post", "/commerce/trx-easy/start/225/", csrf),
            ("get", "/commerce/trx-easy/start/72/", csrf),
            ("post", "/commerce/trx-easy/start/72/", ""),
        ):
            with self.subTest(method=method, action=action):
                html = f'<form method="{method}" action="{action}">{token}{button}</form>'
                self.assertFalse(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def test_hidden_email_id_is_rejected(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">'
                '<input name="contact" id="email-field" type="hidden">'
                '<button type="submit">Create my TRX payment invoice</button></form>')
        result = AUDIT.parse_checkout(html, 72)
        self.assertEqual(result["named_email_inputs"], 1)
        self.assertFalse(result["checkout_post_csrf_cta_valid"])

    def test_unclosed_invoice_form_is_not_accepted(self):
        csrf = '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">'
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                + csrf + '<button type="submit">Create my TRX payment invoice</button>')
        self.assertFalse(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def test_button_with_override_or_disabled_is_not_accepted(self):
        csrf = '<input name="csrfmiddlewaretoken" type="hidden" value="' + 'a' * 64 + '">'
        for override in ('formaction="/other/"', 'formmethod="get"',
                         'form="another"', 'disabled'):
            with self.subTest(override=override):
                html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                        + csrf + '<button type="submit" ' + override
                        + '>Create my TRX payment invoice</button></form>')
                self.assertFalse(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def test_csrf_attached_to_other_form_or_disabled_is_not_accepted(self):
        for override in ('form="another"', 'disabled'):
            with self.subTest(override=override):
                html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                        '<input name="csrfmiddlewaretoken" type="hidden" value="'
                        + 'a' * 64 + '" ' + override + '>'
                        '<button type="submit">Create my TRX payment invoice</button>'
                        '</form>')
                self.assertFalse(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def test_valid_submit_input_is_accepted(self):
        html = ('<form method="post" action="/commerce/trx-easy/start/72/">'
                '<input name="csrfmiddlewaretoken" type="hidden" value="'
                + 'a' * 64 + '">'
                '<input type="submit" value="Create my TRX payment invoice"></form>')
        self.assertTrue(AUDIT.parse_checkout(html, 72)["checkout_post_csrf_cta_valid"])

    def _live_report(self, pages):
        output = io.StringIO()

        def local_get(path):
            return pages[path]

        with patch.object(AUDIT, "fetch", side_effect=local_get):
            with redirect_stdout(output):
                exit_code = AUDIT.live()
        raw = output.getvalue().strip().split("MPW_3SKU_LIVE_FORM_READONLY=", 1)[1]
        return exit_code, json.loads(raw)

    def _safe_page(self, sku):
        return (
            '<form action="/commerce/trx-easy/start/' + str(sku)
            + '/" method="post">'
            + '<input type="hidden" name="csrfmiddlewaretoken" value="'
            + 'a' * 64 + '">'
            + '<button type="submit">Create my TRX payment invoice</button>'
            + '</form>'
        )

    def test_live_success_is_only_form_evidence_not_sale(self):
        pages = {"/store/": (200, "<main>Dynamic storefront</main>")}
        for sku in AUDIT.SKUS:
            pages[f"/store/product/{sku}/checkout/"] = (200, self._safe_page(sku))
        code, report = self._live_report(pages)
        self.assertEqual(code, 0)
        self.assertEqual(report["form_gate"], "PASS")
        self.assertEqual(report["status"], "FORM_ONLY_VERIFIED_SALE_UNPROVEN")
        self.assertFalse(report["sale_proven"])
        self.assertEqual(report["payments"], 0)

    def test_live_email_form_blocks_process_exit(self):
        pages = {"/store/": (200, "<main>Dynamic storefront</main>")}
        for sku in AUDIT.SKUS:
            pages[f"/store/product/{sku}/checkout/"] = (200, self._safe_page(sku))
        pages["/store/product/225/checkout/"] = (
            200, self._safe_page(225).replace(
                "</form>", '<input name="email" type="email" required></form>')
        )
        code, report = self._live_report(pages)
        self.assertEqual(code, 3)
        self.assertFalse(report["all_email_free_forms"])
        self.assertEqual(report["form_gate"], "BLOCKED")
        self.assertFalse(report["sale_proven"])

    def test_live_static_storefront_blocks_green_result(self):
        pages = {"/store/": (200, "<!-- MPW_STATIC_STORE_FALLBACK_V1 -->")}
        for sku in AUDIT.SKUS:
            pages[f"/store/product/{sku}/checkout/"] = (200, self._safe_page(sku))
        code, report = self._live_report(pages)
        self.assertEqual(code, 3)
        self.assertEqual(report["store_mode"], "STATIC_FALLBACK")
        self.assertEqual(report["form_gate"], "BLOCKED")

    def test_live_http_error_reports_numeric_status_without_url(self):
        pages = {"/store/": (200, "<main>Dynamic storefront</main>")}
        for sku in AUDIT.SKUS:
            pages[f"/store/product/{sku}/checkout/"] = (200, self._safe_page(sku))

        def getter(path):
            if path == "/store/product/72/checkout/":
                raise urllib.error.HTTPError(
                    "https://mojplaywin.com/store/product/72/checkout/?secret=DO_NOT_PRINT",
                    404, "not found", {}, None
                )
            return pages[path]

        output = io.StringIO()
        with patch.object(AUDIT, "fetch", side_effect=getter):
            with redirect_stdout(output):
                code = AUDIT.live()
        report = json.loads(output.getvalue().split(
            "MPW_3SKU_LIVE_FORM_READONLY=", 1)[1])
        self.assertEqual(code, 3)
        self.assertEqual(report["products"]["72"]["http_status"], 404)
        self.assertEqual(report["products"]["72"]["error_type"], "HTTPError")
        self.assertNotIn("DO_NOT_PRINT", output.getvalue())
        self.assertFalse(report["sale_proven"])

    def test_live_storefront_503_is_reported_as_status_not_sale(self):
        pages = {f"/store/product/{sku}/checkout/": (200, self._safe_page(sku))
                 for sku in AUDIT.SKUS}

        def getter(path):
            if path == "/store/":
                raise urllib.error.HTTPError(
                    "https://mojplaywin.com/store/", 503, "temporarily unavailable",
                    {}, None
                )
            return pages[path]

        output = io.StringIO()
        with patch.object(AUDIT, "fetch", side_effect=getter):
            with redirect_stdout(output):
                code = AUDIT.live()
        report = json.loads(output.getvalue().split(
            "MPW_3SKU_LIVE_FORM_READONLY=", 1)[1])
        self.assertEqual(code, 3)
        self.assertEqual(report["store_http_status"], 503)
        self.assertFalse(report["all_email_free_forms"])

    def test_live_missing_checkout_is_blocked_not_silenced(self):
        pages = {"/store/": (200, "<main>Dynamic storefront</main>")}
        for sku in (72, 225):
            pages[f"/store/product/{sku}/checkout/"] = (200, self._safe_page(sku))
        with patch.object(AUDIT, "fetch", side_effect=lambda path:
                          pages[path] if path in pages else
                          (_ for _ in ()).throw(OSError("not found"))):
            output = io.StringIO()
            with redirect_stdout(output):
                code = AUDIT.live()
            report = json.loads(output.getvalue().split("MPW_3SKU_LIVE_FORM_READONLY=", 1)[1])
        self.assertEqual(code, 3)
        self.assertFalse(report["products"]["879"]["email_free_form_evidence"])
        self.assertEqual(report["products"]["879"]["error_type"], "OSError")

    def test_no_form_cannot_pass_by_copy(self):
        result = AUDIT.parse_checkout('<h1>Create my TRX payment invoice</h1>')
        self.assertEqual(result["form_count"], 0)
        self.assertFalse(result["trx_invoice_cta_present"])

    def test_copyright_license_or_receipt_not_inferred(self):
        self.assertFalse(AUDIT.parse_checkout('<form></form>')["email_label_present"])
        self.assertEqual(AUDIT.SKUS, (72, 225, 879))


if __name__ == "__main__":
    unittest.main()
