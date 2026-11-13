"""Offline contract tests for GET-only MojPlayWin public audit."""
import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts/mpw_onepass_public_sales_audit_20261113.py"
SPEC = importlib.util.spec_from_file_location("mpw_onepass_public_sales", PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def checkout(sku, extra=""):
    return (
        "<html><title>MojPlayWin</title><body><main>"
        f'<form method="post" action="/commerce/trx-easy/start/{sku}/">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="nonempty"/>'
        + extra + "</form></main></body></html>"
    )


class AuditTests(unittest.TestCase):
    def test_no_email_checkout_get_not_payment(self):
        self.assertEqual(
            MOD.classify_html("checkout", 72, checkout(72)),
            "no_email_checkout_get_ok_not_paid")

    def test_email_form_is_explicit_mismatch(self):
        self.assertEqual(
            MOD.classify_html("checkout", 72,
                checkout(72, '<input type="email" name="email" required>')),
            "legacy_email_requested")

    def test_wrong_product_post_action_fails(self):
        self.assertEqual(
            MOD.classify_html("checkout", 225, checkout(72)),
            "checkout_post_action_unverified")

    def test_missing_csrf_fails(self):
        html = checkout(879).replace('value="nonempty"', 'value=""')
        self.assertEqual(
            MOD.classify_html("checkout", 879, html),
            "checkout_csrf_unverified")

    def test_static_fallback_not_dynamic(self):
        html = ("<html><title>MojPlayWin</title><body>"
                "MPW_STATIC_STORE_FALLBACK_V1" + "x"*160 + "</body></html>")
        self.assertEqual(
            MOD.classify_html("store", None, html),
            "static_fallback_not_dynamic")

    def test_short_page_never_passes(self):
        self.assertEqual(
            MOD.classify_html("detail", 72, "<h1>MojPlayWin</h1>"),
            "unexpected_short_page")

    def test_external_form_action_rejected(self):
        html = checkout(72).replace(
            'action="/commerce/', 'action="https://evil.example/commerce/')
        self.assertEqual(
            MOD.classify_html("checkout", 72, html),
            "checkout_post_action_unverified")

    def test_zero_financial_actions_and_unknown_sales(self):
        class Offline:
            def open(self, req, timeout=None):
                raise OSError("deliberate network isolation")
        result = MOD.audit(opener=Offline())
        self.assertEqual(result["pages_checked"], 10)
        self.assertEqual(set(result["observed_routes"].values()),
                         {"network_unavailable_not_outage_proof"})
        self.assertIsNone(result["commercial_sales_verified"])
        self.assertFalse(result["payments_sent"])
        self.assertFalse(result["payment_or_invoice_posts_performed"])


if __name__ == "__main__":
    unittest.main()
