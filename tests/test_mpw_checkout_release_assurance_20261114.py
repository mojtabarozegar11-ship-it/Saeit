"""No network, money, emails or customer data: release-GET regression contracts."""
import unittest

from services.mpw_checkout_release_assurance import (
    checkout_release_get_category as classify,
    CHECKOUT_BODY_OK, FORM_NOT_PROVEN, BODY_NOT_PROVEN,
    CONTENT_TYPE_NOT_PROVEN, CSP_MISSING, CSP_DUPLICATE, CSP_SCRIPT,
    CSP_FORM, CSP_FRAME, CSP_BASE, CACHE_NOT_PROVEN,
)

EMAIL = '<input type="email" name="email" required maxlength="254" autocomplete="email">'
CSRF = '<input type="hidden" name="csrfmiddlewaretoken" value="' + 'A'*64 + '">'
SUBMIT = '<button type="submit">Create TRX payment invoice</button>'
FORM = '<form method="post" action="/commerce/trx-easy/start/72/">'
CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "script-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
HEADER = {"Content-Type":"text/html; charset=utf-8",
          "Content-Security-Policy":CSP,
          "Cache-Control":"private, no-store, max-age=0"}


def document():
    return ('<!doctype html><html><head><title>MojPlayWin — buyer checkout</title></head>'
            '<body><main><h1>Checkout a digital item</h1>' +
            FORM + CSRF + EMAIL + SUBMIT + '</form></main></body></html>').encode()


class BuyerEmailReleaseGetGate(unittest.TestCase):
    def check(self, body=None, headers=None, sku=72):
        return classify(document() if body is None else body,
                        HEADER if headers is None else headers, sku)

    def test_01_expected_form_and_security_headers_classify_get_only(self):
        self.assertEqual(self.check(), CHECKOUT_BODY_OK)

    def test_02_get_is_not_claim_of_payment(self):
        self.assertIn("not_paid", self.check())

    def test_03_absent_email_blocks_purchase(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(), b"")), FORM_NOT_PROVEN)

    def test_04_optional_email_blocks_purchase(self):
        self.assertEqual(self.check(document().replace(b" required maxlength", b" maxlength")), FORM_NOT_PROVEN)

    def test_05_buyer_email_in_disabled_fieldset_blocks(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(),
            b"<fieldset disabled>"+EMAIL.encode()+b"</fieldset>")), FORM_NOT_PROVEN)

    def test_06_hidden_email_blocks(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(),
            EMAIL[:-1].encode()+b" hidden>")), FORM_NOT_PROVEN)

    def test_07_aria_hidden_email_blocks(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(),
            EMAIL[:-1].encode()+b' aria-hidden="true">')), FORM_NOT_PROVEN)

    def test_08_invalid_inputmode_blocks_mobile(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(),
            EMAIL[:-1].encode()+b' inputmode="none">')), FORM_NOT_PROVEN)

    def test_09_two_buyer_emails_are_ambiguous(self):
        self.assertEqual(self.check(document().replace(EMAIL.encode(),
            (EMAIL+EMAIL).encode())), FORM_NOT_PROVEN)

    def test_10_wrong_sku_action_rejected(self):
        self.assertEqual(self.check(sku=225), FORM_NOT_PROVEN)

    def test_11_missing_csrf_rejected(self):
        self.assertEqual(self.check(document().replace(CSRF.encode(), b"")), FORM_NOT_PROVEN)

    def test_12_csrf_too_short_rejected(self):
        self.assertEqual(self.check(document().replace(('A'*64).encode(), b"short")), FORM_NOT_PROVEN)

    def test_13_missing_submit_rejected(self):
        self.assertEqual(self.check(document().replace(SUBMIT.encode(), b"")), FORM_NOT_PROVEN)

    def test_14_disabled_submit_rejected(self):
        self.assertEqual(self.check(document().replace(b'type="submit"', b'type="submit" disabled')), FORM_NOT_PROVEN)

    def test_15_form_novalidate_rejected(self):
        self.assertEqual(self.check(document().replace(b'method="post"', b'method="post" novalidate')), FORM_NOT_PROVEN)

    def test_16_html_unsafe_inline_script_rejected(self):
        self.assertEqual(self.check(document().replace(b"</main>", b"<script>alert(1)</script></main>")), FORM_NOT_PROVEN)

    def test_17_null_headers_rejected(self):
        self.assertEqual(self.check(headers={}), CONTENT_TYPE_NOT_PROVEN)

    def test_18_wrong_content_type_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Type":"application/json"}), CONTENT_TYPE_NOT_PROVEN)

    def test_19_missing_csp_rejected(self):
        h={**HEADER};h.pop("Content-Security-Policy")
        self.assertEqual(self.check(headers=h), CSP_MISSING)

    def test_20_csp_script_missing_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("script-src 'none'; ", "")}), CSP_SCRIPT)

    def test_21_unsafe_inline_script_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("script-src 'none'","script-src 'unsafe-inline'")}), CSP_SCRIPT)

    def test_22_script_self_is_not_exact_none(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("script-src 'none'","script-src 'self'")}), CSP_SCRIPT)

    def test_23_duplicate_script_directive_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP+"; script-src 'none'"}), CSP_DUPLICATE)

    def test_24_duplicate_frame_ancestors_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP+"; frame-ancestors 'none'"}), CSP_DUPLICATE)

    def test_25_missing_form_action_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("form-action 'self'; ","")}), CSP_FORM)

    def test_26_foreign_form_action_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("form-action 'self'","form-action https://example.org")}), CSP_FORM)

    def test_27_missing_frame_ancestors_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("; frame-ancestors 'none'","")}), CSP_FRAME)

    def test_28_frame_ancestors_self_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("frame-ancestors 'none'","frame-ancestors 'self'")}), CSP_FRAME)

    def test_29_missing_base_uri_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("base-uri 'self'; ","")}), CSP_BASE)

    def test_30_base_uri_none_also_allowed(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":CSP.replace("base-uri 'self'","base-uri 'none'")}), CHECKOUT_BODY_OK)

    def test_31_missing_no_store_rejected(self):
        self.assertEqual(self.check(headers={**HEADER,"Cache-Control":"private"}), CACHE_NOT_PROVEN)

    def test_32_no_cache_not_equivalent_to_no_store(self):
        self.assertEqual(self.check(headers={**HEADER,"Cache-Control":"no-cache, private"}), CACHE_NOT_PROVEN)

    def test_33_case_insensitive_cache_header_value(self):
        self.assertEqual(self.check(headers={**HEADER,"Cache-Control":"PRIVATE, NO-STORE"}), CHECKOUT_BODY_OK)

    def test_34_no_store_equals_true_is_not_standard_token(self):
        self.assertEqual(self.check(headers={**HEADER,"Cache-Control":"private, no-store=true"}), CACHE_NOT_PROVEN)

    def test_35_reject_csp_header_longer_than_limit(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Security-Policy":"a"*4097}), CSP_MISSING)

    def test_36_reject_missing_body(self):
        self.assertEqual(self.check(body=b""), FORM_NOT_PROVEN)

    def test_37_reject_non_bytes_body(self):
        self.assertEqual(self.check(body="<html>"), BODY_NOT_PROVEN)

    def test_38_reject_boolean_product_id(self):
        self.assertEqual(self.check(sku=True), BODY_NOT_PROVEN)

    def test_39_reject_wrong_email_field_name(self):
        self.assertEqual(self.check(document().replace(b'name="email"',b'name="receiver"')), FORM_NOT_PROVEN)

    def test_40_does_not_return_any_csrf_email_or_HTML_bytes(self):
        self.assertNotIn("AAAA", self.check())
        self.assertNotIn("<", self.check())

    def test_41_wont_accept_content_type_html_like_prefix(self):
        self.assertEqual(self.check(headers={**HEADER,"Content-Type":"text/html-malicious"}), CONTENT_TYPE_NOT_PROVEN)

    def test_42_reject_untrusted_active_script_scheme(self):
        html=document().replace(b"</main>", b'<a href="javascript:alert(1)">Help</a></main>')
        self.assertEqual(self.check(html), FORM_NOT_PROVEN)
