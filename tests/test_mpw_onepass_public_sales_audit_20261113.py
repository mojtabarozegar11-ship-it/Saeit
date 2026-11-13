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
        '<input type="hidden" name="csrfmiddlewaretoken" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"/>'
        '<button type="submit">Create TRX invoice</button>'
        + extra + "</form></main></body></html>"
    )


class AuditTests(unittest.TestCase):
    def test_no_email_checkout_get_not_payment(self):
        self.assertEqual(
            MOD.classify_html("checkout", 72, checkout(72)),
            "buyer_email_input_unverified")

    def test_required_buyer_email_field_is_seen_but_not_server_verified(self):
        self.assertEqual(
            MOD.classify_html("checkout", 72,
                checkout(72, '<input type="email" name="email" required>')),
            "buyer_email_input_get_ok_not_paid")

    def test_optional_disabled_and_spoofed_buyer_email_fields_are_rejected(self):
        for html_field in (
            '<input type="email" name="email">',
            '<input type="email" name="email" required disabled>',
            '<input type="email" name="email" required readonly>',
            '<input type="text" name="email" required>',
            '<input type="email" name="contact" required>',
            '<input type="email" name="email" required>'
            '<input type="email" name="buyer_email" required>',
        ):
            with self.subTest(field=html_field):
                self.assertEqual(
                    MOD.classify_html("checkout", 72, checkout(72, html_field)),
                    "buyer_email_input_unverified")

    def test_wrong_product_post_action_fails(self):
        self.assertEqual(
            MOD.classify_html("checkout", 225, checkout(72)),
            "checkout_post_action_unverified")

    def test_missing_csrf_fails(self):
        html = checkout(879).replace('value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"', 'value=""')
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
        html = checkout(72).replace('name="csrfmiddlewaretoken" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"', 'name="other" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"')
        html += '<input type="hidden" name="csrfmiddlewaretoken" value="forged">'
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_csrf_in_unrelated_form_does_not_validate_purchase(self):
        html = checkout(72).replace('name="csrfmiddlewaretoken" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"', 'name="other" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"')
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
            "checkout_csp_missing")

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
                         "checkout_csp_scripts_unverified")

    def test_security_headers_reject_unsafe_scripts(self):
        headers = {
            "Content-Security-Policy":
                "script-src 'none' 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'",
            "Cache-Control": "no-store",
        }
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_csp_scripts_unverified")

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
                         "buyer_email_input_unverified")

    def test_wrong_sku_rejected_before_form_lookup(self):
        self.assertEqual(MOD.classify_html("checkout", 779, checkout(72)),
                         "invalid_sku")

    def test_missing_form_action_category(self):
        headers = {"Content-Security-Policy":
                   "script-src 'none'; frame-ancestors 'none'",
                   "Cache-Control": "no-store"}
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_csp_form_action_unverified")

    def test_missing_frame_ancestors_category(self):
        headers = {"Content-Security-Policy":
                   "script-src 'none'; form-action 'self'",
                   "Cache-Control": "no-store"}
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_csp_frames_unverified")

    def test_missing_script_src_category(self):
        headers = {"Content-Security-Policy":
                   "form-action 'self'; frame-ancestors 'none'",
                   "Cache-Control": "no-store"}
        self.assertEqual(MOD.checkout_header_status(headers),
                         "checkout_csp_scripts_unverified")

    def test_checkout_form_is_reported_despite_missing_csp(self):
        page = checkout(72).encode("utf-8")
        url = "https://mojplaywin.com/store/product/72/checkout/"
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "text/html",
                       "Cache-Control": "no-store"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return url
            def read(self, length):
                return page[:length]
        class FakeOpener:
            def open(self, request, timeout=None):
                self.last_method = request.get_method()
                return FakeResponse()
        client = FakeOpener()
        forms = {}
        status = MOD.observe("/store/product/72/checkout/", "checkout",
                             72, 4, client, forms)
        self.assertEqual(client.last_method, "GET")
        self.assertEqual(status, "checkout_csp_missing")
        self.assertEqual(forms["/store/product/72/checkout/"],
                         "buyer_email_input_unverified")

    def test_weak_csrf_rejected(self):
        html = checkout(72).replace("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "tiny")
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_non_alphanumeric_csrf_rejected(self):
        html = checkout(72).replace("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "A" * 63 + "-")
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_valid_32_character_csrf_token(self):
        html = checkout(72).replace("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "Z" * 32)
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_disabled_csrf_rejected(self):
        html = checkout(72).replace('name="csrfmiddlewaretoken"',
                                    'name="csrfmiddlewaretoken" disabled')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_duplicate_csrf_rejected(self):
        html = checkout(72, '<input type="hidden" name="csrfmiddlewaretoken" value="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_csrf_unverified")

    def test_no_submit_control_rejected(self):
        html = checkout(72).replace('<button type="submit">Create TRX invoice</button>', "")
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_submit_control_unverified")

    def test_disabled_submit_rejected(self):
        html = checkout(72).replace('type="submit">', 'type="submit" disabled>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_submit_control_unverified")

    def test_button_type_button_not_submit(self):
        html = checkout(72).replace('type="submit">', 'type="button">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_submit_control_unverified")

    def test_input_submit_accepted(self):
        html = checkout(72).replace('<button type="submit">Create TRX invoice</button>',
                                    '<input type="submit" value="Start order">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_button_default_type_submit_accepted(self):
        html = checkout(72).replace('type="submit">', '>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_email_alias_id_detected(self):
        html = checkout(72, '<input id="mpw-buy-email" name="contact">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_email_autocomplete_detected(self):
        html = checkout(72, '<input name="contact" autocomplete="email">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_email_textarea_detected(self):
        html = checkout(72, '<textarea name="buyer_email"></textarea>')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "buyer_email_input_unverified")

    def test_duplicate_form_method_rejected(self):
        html = checkout(72).replace('method="post"', 'method="post" method="get"')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_duplicate_form_action_rejected(self):
        html = checkout(72).replace('action="/commerce/trx-easy/start/72/"',
                                    'action="/commerce/trx-easy/start/72/" action="/evil/"')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def _fake_observe(self, page, *, final_url=None, content_type="text/html",
                      status=200, headers=None):
        path = "/store/product/72/checkout/"
        class FakeResponse:
            def __init__(self):
                self.status = status
                self.headers = headers or {
                    "Content-Type": content_type,
                    "Content-Security-Policy":
                        "script-src 'none'; form-action 'self'; frame-ancestors 'none'",
                    "Cache-Control": "no-store"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return final_url or "https://mojplaywin.com" + path
            def read(self, size):
                return page.encode("utf-8")[:size] if isinstance(page, str) else page[:size]
        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()
        forms = {}
        result = MOD.observe(path, "checkout", 72, 4, FakeOpener(), forms)
        return result, forms

    def test_external_base_redirects_form_and_is_rejected(self):
        html = checkout(72).replace("<main>",
                                    '<main><base href="https://evil.example/">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_base_href_unverified")

    def test_self_base_is_rejected_pending_source_review(self):
        html = checkout(72).replace("<main>", '<main><base href="/store/">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_base_href_unverified")

    def test_duplicated_name_on_csrf_is_rejected(self):
        html = checkout(72).replace('name="csrfmiddlewaretoken"',
                                    'name="bogus" name="csrfmiddlewaretoken"')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_duplicate_button_type_is_rejected(self):
        html = checkout(72).replace('type="submit">', 'type="button" type="submit">')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_invoice_action_query_string_is_rejected(self):
        html = checkout(72).replace('action="/commerce/trx-easy/start/72/"',
                                    'action="/commerce/trx-easy/start/72/?next=evil"')
        self.assertEqual(MOD.classify_html("checkout", 72, html),
                         "checkout_post_action_unverified")

    def test_catalog_cta_query_is_not_verified(self):
        paths = ('/store/product/72/checkout/',
                 '/store/product/225/checkout/', '/store/product/879/')
        html = '<html><title>MojPlayWin</title>' + ' ' * 170
        html += ''.join('<a href="' + p + '?next=evil">View product</a>' for p in paths)
        self.assertEqual(MOD.classify_html("store", None, html),
                         "catalog_ctas_unverified")

    def test_product_detail_cta_query_is_not_verified(self):
        html = ('<html><title>MojPlayWin</title>'
                '<a href="/store/product/72/checkout/?next=evil">Buy</a>'
                + ' ' * 170)
        self.assertEqual(MOD.classify_html("detail", 72, html),
                         "detail_product_identity_unverified")

    def test_relative_or_external_paths_fail_same_origin_gate(self):
        for raw in ("store/product/72/checkout/", "//evil.example/checkout/",
                    "https://evil.example/store/product/72/checkout/"):
            with self.subTest(path=raw):
                self.assertEqual(MOD._local_path(raw), "")

    def test_public_observer_rejects_wrong_https_port(self):
        status, forms = self._fake_observe(checkout(72),
            final_url="https://mojplaywin.com:444/store/product/72/checkout/")
        self.assertEqual(status, "unexpected_destination")
        self.assertEqual(forms, {})

    def test_public_observer_rejects_http_downgrade(self):
        status, forms = self._fake_observe(checkout(72),
            final_url="http://mojplaywin.com/store/product/72/checkout/")
        self.assertEqual(status, "unexpected_destination")
        self.assertEqual(forms, {})

    def test_public_observer_requires_actual_html_content_type(self):
        status, forms = self._fake_observe(checkout(72),
            content_type="application/x-text/html-diff")
        self.assertEqual(status, "unexpected_content_type")
        self.assertEqual(forms, {})

    def test_public_observer_accepts_standard_html_charset(self):
        status, forms = self._fake_observe(checkout(72), headers={
            "Content-Type": "text/html; charset=utf-8",
            "Content-Security-Policy":
                "script-src 'none'; form-action 'self'; frame-ancestors 'none'",
            "Cache-Control": "no-store"})
        self.assertEqual(status, "buyer_email_input_unverified")
        self.assertEqual(forms["/store/product/72/checkout/"],
                         "buyer_email_input_unverified")

    def test_large_html_body_fails_without_parsing(self):
        status, forms = self._fake_observe(b"x" * (MOD.MAX_BODY + 1))
        self.assertEqual(status, "body_over_limit")
        self.assertEqual(forms, {})

    def test_http_503_is_not_misreported_as_zero_sales(self):
        from urllib.error import HTTPError
        class Offline:
            def open(self, req, timeout=None):
                raise HTTPError(req.full_url, 503, "unavailable", {}, None)
        result = MOD.audit(opener=Offline())
        self.assertEqual(set(result["observed_routes"].values()), {"http_503"})
        self.assertIsNone(result["commercial_sales_verified"])

    def test_http_307_redirect_is_not_followed(self):
        from urllib.error import HTTPError
        class Redirect:
            def open(self, req, timeout=None):
                raise HTTPError(req.full_url, 307, "temporary", {}, None)
        result = MOD.audit(opener=Redirect())
        self.assertEqual(set(result["observed_routes"].values()),
                         {"redirect_not_followed"})
        self.assertFalse(result["payments_sent"])

    def test_script_policy_categories_do_not_emit_raw_headers(self):
        scenarios = {
            "csp_missing": "",
            "script_src_missing": "default-src 'self'; form-action 'self'",
            "script_src_duplicate": "script-src 'none'; script-src 'self'",
            "script_none": "script-src 'none'",
            "script_self_only": "script-src 'self'",
            "script_unsafe_inline_or_eval": "script-src 'self' 'unsafe-inline'",
            "script_wildcard_or_http": "script-src http: *",
            "script_nonce_or_hash": "script-src 'self' 'nonce-nonlogged-testtoken'",
            "script_other": "script-src https://cdn.example.org",
        }
        for expected, value in scenarios.items():
            with self.subTest(category=expected):
                got = MOD.script_csp_category({"Content-Security-Policy": value})
                self.assertEqual(got, expected)
                self.assertNotIn("nonlogged-testtoken", got)
                self.assertNotIn("cdn.example.org", got)
                self.assertLess(len(got), 55)

    def test_audit_records_sanitized_policy_but_not_buyer_data(self):
        from urllib.error import HTTPError
        class NoNetwork:
            def open(self, req, timeout=None):
                raise HTTPError(req.full_url, 503, "unavailable", {}, None)
        result = MOD.audit(opener=NoNetwork())
        self.assertEqual(result["checkout_script_policy_categories"], {})
        self.assertIsNone(result["commercial_sales_verified"])
        self.assertFalse(result["customer_data_read"])

    def test_observer_keeps_header_category_separate_from_checkout_form(self):
        class FakeResponse:
            status = 200
            headers = {"Content-Type": "text/html",
                       "Cache-Control": "no-store",
                       "Content-Security-Policy":
                           "script-src 'self'; form-action 'self'; frame-ancestors 'none'"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "https://mojplaywin.com/store/product/72/checkout/"
            def read(self, n):
                return checkout(72).encode()
        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()
        form = {}
        policies = {}
        state = MOD.observe("/store/product/72/checkout/", "checkout", 72,
                            5, FakeOpener(), form, policies)
        self.assertEqual(state, "checkout_csp_scripts_unverified")
        self.assertEqual(form["/store/product/72/checkout/"],
                         "buyer_email_input_unverified")
        self.assertEqual(policies["/store/product/72/checkout/"],
                         "script_self_only")

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
