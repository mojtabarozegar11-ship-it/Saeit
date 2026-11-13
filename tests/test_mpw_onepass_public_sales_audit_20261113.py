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

    def test_csrf_outside_form_does_not_validate_purchase(self):
        html = checkout(72).replace('name="csrfmiddlewaretoken" value="nonempty"', 'name="other" value="nonempty"')
        html += '<input type="hidden" name="csrfmiddlewaretoken" value="forged">'
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_csrf_in_unrelated_form_does_not_validate_purchase(self):
        html = checkout(72).replace('name="csrfmiddlewaretoken" value="nonempty"', 'name="other" value="nonempty"')
        html += ('<form method="post" action="/different/">'
                 '<input name="csrfmiddlewaretoken" value="forged"></form>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_form_ambiguous")

    def test_nested_forms_rejected_before_checkout(self):
        html = ('<html><title>MojPlayWin</title>' + " " * 160
                + '<form method="post" action="/commerce/trx-easy/start/72/">'
                + '<form method="post" action="/different/">'
                + '<input name="csrfmiddlewaretoken" value="token"></form>'
                + '</form></html>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_store_links_not_comment_strings(self):
        paths = ('/store/product/72/checkout/',
                 '/store/product/225/checkout/', '/store/product/879/')
        html = "<html><title>MojPlayWin</title>" + " " * 180
        html += "<!-- " + " ".join(paths) + " -->"
        self.assertEqual(MOD.classify_html("store", None, html),
                         "catalog_ctas_unverified")

    def test_store_valid_three_product_links(self):
        paths = ('/store/product/72/checkout/',
                 '/store/product/225/checkout/', '/store/product/879/')
        html = "<html><title>MojPlayWin</title>" + " " * 180
        html += "".join(f'<a href="{p}">View product</a>' for p in paths)
        self.assertEqual(MOD.classify_html("store", None, html),
                         "store_public_get_ok_not_sale")

    def test_detail_numbers_in_css_not_evidence_of_product(self):
        html = '<html><title>MojPlayWin</title><style>width:72px</style>' + " " * 180
        self.assertEqual(MOD.classify_html("detail", 72, html),
                         "detail_product_identity_unverified")

    def test_detail_requires_matching_checkout_cta(self):
        html = ('<html><title>MojPlayWin</title>'
                '<a href="/store/product/225/checkout/">Buy</a>' + " " * 170)
        self.assertEqual(MOD.classify_html("detail", 72, html),
                         "detail_product_identity_unverified")
        self.assertEqual(MOD.classify_html("detail", 225, html),
                         "detail_public_get_ok_not_sale")

    def test_missing_method_does_not_crash(self):
        html = checkout(72).replace('method="post"', 'method')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_no_implicit_purchase_when_network_down(self):
        class FailedResponse:
            def open(self, request, timeout=None):
                raise TimeoutError("timeout")
        statuses = MOD.audit(opener=FailedResponse())["observed_routes"]
        self.assertEqual(len(statuses), 10)
        self.assertEqual(set(statuses.values()),
                         {"network_unavailable_not_outage_proof"})

    def test_security_headers_strict_valid(self):
        headers = {
            "Content-Security-Policy":
                "default-src 'self'; script-src 'none'; form-action 'self'; "
                "frame-ancestors 'none'; style-src 'self' 'unsafe-inline'",
            "Cache-Control": "private, no-cache, no-store",
        }
        self.assertEqual(MOD.checkout_header_status(headers), "checkout_headers_pass")

    def test_security_headers_missing_csp(self):
        self.assertEqual(
            MOD.checkout_header_status({"Cache-Control": "no-store"}),
            "checkout_security_headers_unverified")

    def test_security_headers_no_store_required(self):
        headers = {
            "Content-Security-Policy":
                "script-src 'none'; form-action 'self'; frame-ancestors 'none'",
            "Cache-Control": "private, no-cache",
        }
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_cache_policy_unverified")

    def test_security_headers_reject_duplicate_script_directives(self):
        headers = {
            "Content-Security-Policy":
                "script-src 'none'; script-src 'self'; form-action 'self'; "
                "frame-ancestors 'none'",
            "Cache-Control": "no-store",
        }
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_security_headers_unverified")

    def test_security_headers_reject_unsafe_scripts(self):
        headers = {
            "Content-Security-Policy":
                "script-src 'none' 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'",
            "Cache-Control": "no-store",
        }
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_security_headers_unverified")

    def test_hidden_csrf_required(self):
        html = checkout(72).replace('type="hidden"', 'type="text"')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_get_only_http_method_contract(self):
        import inspect
        source = inspect.getsource(MOD.observe)
        self.assertIn('method="GET"', source)
        self.assertNotIn('method="POST"', source)

    def test_competing_external_post_form_is_ambiguous(self):
        html = (checkout(72) +
                '<form method="POST" action="https://evil.example/collect">'
                '<input name="email" type="email"></form>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_form_ambiguous")

    def test_two_matching_checkout_forms_are_ambiguous(self):
        html = checkout(72) + checkout(72)
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_form_ambiguous")

    def test_unclosed_checkout_form_is_not_certified(self):
        html = checkout(72).replace("</form>", "")
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_unrelated_get_search_form_is_not_checkout_post(self):
        html = checkout(72) + '<form method="GET" action="/search/">Search</form>'
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "no_email_checkout_get_ok_not_paid")

    def test_wrong_sku_rejected_before_form_lookup(self):
        self.assertEqual(MOD.classify_html("checkout", 779, checkout(72)),
                         "invalid_sku")

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
