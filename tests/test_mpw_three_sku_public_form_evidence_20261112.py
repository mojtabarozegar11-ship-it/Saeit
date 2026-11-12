"""Offline contract tests for the read-only public checkout audit."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

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

    def test_no_form_cannot_pass_by_copy(self):
        result = AUDIT.parse_checkout('<h1>Create my TRX payment invoice</h1>')
        self.assertEqual(result["form_count"], 0)
        self.assertFalse(result["trx_invoice_cta_present"])

    def test_copyright_license_or_receipt_not_inferred(self):
        self.assertFalse(AUDIT.parse_checkout('<form></form>')["email_label_present"])
        self.assertEqual(AUDIT.SKUS, (72, 225, 879))


if __name__ == "__main__":
    unittest.main()
