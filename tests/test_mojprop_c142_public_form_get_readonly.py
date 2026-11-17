"""No external HTTP: adversarial checks of C142 live GET-only classifier."""
import socket
import ssl
import unittest
from urllib.error import HTTPError, URLError

from scripts.mojprop_c142_public_form_get_readonly import (
    ENDPOINTS, MAX_BYTES, evaluate_page, probe_one,
)

def form(locale="en", direction="ltr"):
    return (f'<!doctype html><html lang="{locale}" dir="{direction}"><head>'
            '<meta name="robots" content="noindex,nofollow"></head><body>'
            'MOJ-PROP-01 30 native TRX. This is not a payment or funded account. '
            '<form method="post" action="/moj-prop-interest/">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="test-only-token">'
            '<input type="hidden" name="plan_code" value="MOJ-PROP-01">'
            '<input type="hidden" name="consent_version" value="moj-prop-interest-v1">'
            f'<input type="hidden" name="source_language" value="{locale}">'
            '<input type="email" name="email" maxlength="254" required>'
            '<input type="checkbox" name="contact_consent" value="yes" required>'
            '<button type="submit">Request information</button>'
            + ('No invoice or settlement happens here. ' * 5) +
            '</form></body></html>').encode("utf-8")

class FakeResponse:
    status = 200
    def __init__(self, body):
        self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, maximum): return self.body[:maximum]


class FakeOpener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url in dict(ENDPOINTS).values()
        assert timeout <= 9
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


class Plan1GetOnlyProbeContract(unittest.TestCase):
    def test_exact_public_https_routes_and_no_credentials(self):
        self.assertEqual(len(ENDPOINTS), 2)
        self.assertEqual(ENDPOINTS[0][0], "en")
        self.assertEqual(ENDPOINTS[1][0], "fa")
        self.assertTrue(all(url.startswith("https://mojplaywin.com/") for _,url in ENDPOINTS))
        self.assertEqual(len({url for _,url in ENDPOINTS}), 2)

    def test_fixture_is_one_html_document_not_a_repeated_prefix(self):
        self.assertEqual(form().count(b"<html"), 1)
        self.assertEqual(form().count(b"<form"), 1)
        self.assertEqual(form().count(b"</form>"), 1)
        self.assertEqual(form("fa", "rtl").count(b"<html"), 1)

    def test_valid_nonpayable_english_and_farsi(self):
        self.assertEqual(evaluate_page(status=200, body=form(), language="en"),
                         "verified_get_form_no_payment_claim")
        self.assertEqual(evaluate_page(status=200, body=form("fa","rtl"), language="fa"),
                         "verified_get_form_no_payment_claim")

    def test_explicit_real_404_and_server_failures_remain_blocking(self):
        for status in (403,404,429,500,502,503,504):
            self.assertEqual(evaluate_page(status=status, body=form(),language="en"),
                             f"http_{status}")

    def test_django_200_without_contact_consent_is_not_success(self):
        html = form().replace(b'name="contact_consent"', b'name="optional_newsletter"')
        self.assertEqual(evaluate_page(status=200,body=html,language="en"),
                         "200_not_a_real_consent_form")

    def test_generic_intake_or_fake_csrf_is_not_a_consent_form(self):
        for body in (
            form().replace(b'/moj-prop-interest/',b'/moj-prop-intake/'),
            form().replace(b'name="csrfmiddlewaretoken"',b'name="fake-csrf"'),
            form().replace(b'value="MOJ-PROP-01"',b'value="MOJPROP-STARTER30"'),
        ):
            self.assertEqual(evaluate_page(status=200,body=body,language="en"),
                             "200_not_a_real_consent_form")

    def test_non_utf8_oversize_or_tiny_body_denied(self):
        self.assertEqual(evaluate_page(status=200,body=b'no',language="en"),"invalid_body")
        self.assertEqual(evaluate_page(status=200,body=b'x'*(MAX_BYTES+1),language="en"),
                         "invalid_body")
        self.assertEqual(evaluate_page(status=200,body=b'\xff'*400,language="en"),
                         "invalid_utf8")

    def test_farsi_must_be_rtl_and_locale_exact(self):
        self.assertEqual(evaluate_page(status=200,body=form("fa","ltr"),language="fa"),
                         "farsi_not_rtl")
        self.assertEqual(evaluate_page(status=200,body=form("en"),language="fa"),
                         "wrong_locale")

    def test_wallet_automation_and_private_key_fields_denied(self):
        for payload in ('tronWeb.trx.sendTransaction', 'walletconnect', 'name="private_key"'):
            html=form()+payload.encode()
            self.assertEqual(evaluate_page(status=200,body=html,language="en"),
                             "forbidden_payment_or_key_field")

    def test_comment_markers_cannot_forge_an_actual_form(self):
        # Strings in HTML comments must not establish a valid CSRF/consent form.
        fake = (b'<!doctype html><html lang="en" dir="ltr"><head>'
                b'<meta name="robots" content="noindex,nofollow"></head><body>'
                b'<!-- '+form().split(b'<form',1)[1]+b' -->'
                b'<p>MOJ PROP public information only.</p></body></html>')
        self.assertEqual(evaluate_page(status=200,body=fake,language="en"),
                         "200_not_a_real_consent_form")

    def test_optional_consent_checkbox_cannot_masquerade_as_opt_in(self):
        optional = form().replace(b' value="yes" required>', b' value="yes">')
        self.assertEqual(evaluate_page(status=200,body=optional,language="en"),
                         "200_not_a_real_consent_form")

    def test_empty_csrf_or_duplicate_consent_denied(self):
        for altered in (
            form().replace(b'value="test-only-token"',b'value=""'),
            form().replace(b'<button type="submit">',
                           b'<input type="checkbox" name="contact_consent" value="yes" required>'
                           b'<button type="submit">'),
            form().replace(b'<input type="email" name="email" maxlength="254" required>',
                           b'<input type="email" name="email" maxlength="254">'),
        ):
            with self.subTest(altered=altered[-60:]):
                self.assertEqual(evaluate_page(status=200,body=altered,language="en"),
                                 "200_not_a_real_consent_form")

    def test_source_language_and_consent_version_are_consistent(self):
        for altered in (
            form("fa","rtl").replace(b'value="fa"',b'value="en"'),
            form().replace(b'moj-prop-interest-v1',b'moj-prop-unknown'),
            form().replace(b'type="hidden" name="plan_code"',
                           b'type="text" name="plan_code"'),
        ):
            self.assertEqual(evaluate_page(status=200,body=altered,
                                           language="fa" if b'lang="fa"' in altered else "en"),
                             "200_not_a_real_consent_form")

    def test_wrong_form_location_multi_form_or_external_script_denied(self):
        for altered in (
            form().replace(b'action="/moj-prop-interest/"',
                           b'action="https://external.example/collect"'),
            form().replace(b'</body>',b'<form method="post"></form></body>'),
            form().replace(b'</body>',b'<script src="/unsafe.js"></script></body>'),
        ):
            self.assertEqual(evaluate_page(status=200,body=altered,language="en"),
                             "200_not_a_real_consent_form")

    def test_noindex_must_be_head_meta_not_body_marker(self):
        forged = form().replace(
            b'<meta name="robots" content="noindex,nofollow">',
            b'<!-- noindex,nofollow --><p>noindex,nofollow</p>')
        self.assertEqual(evaluate_page(status=200,body=forged,language="en"),
                         "200_not_a_real_consent_form")

    def test_only_get_and_no_post_after_http_200(self):
        result=probe_one(FakeOpener(FakeResponse(form())), "en", ENDPOINTS[0][1])
        self.assertTrue(result["get_form_verified"])
        self.assertEqual(result["http_status"],200)

    def test_404_classification_does_not_masquerade_as_200(self):
        err=HTTPError(ENDPOINTS[0][1],404,"Not Found",{},None)
        result=probe_one(FakeOpener(err),"en",ENDPOINTS[0][1])
        self.assertFalse(result["get_form_verified"])
        self.assertEqual(result["state"],"http_404")

    def test_dns_tls_and_timeout_cannot_be_misclassified_as_http_404(self):
        cases = (
            (URLError(socket.gaierror(socket.EAI_NONAME, "synthetic DNS")), "dns_unavailable"),
            (URLError(ssl.SSLError("synthetic TLS error")), "tls_failed"),
            (URLError(TimeoutError("synthetic timeout")), "network_timeout"),
        )
        for error, state in cases:
            with self.subTest(state=state):
                result = probe_one(FakeOpener(error), "en", ENDPOINTS[0][1])
                self.assertEqual(result["state"], state)
                self.assertIsNone(result["http_status"])
                self.assertFalse(result["get_form_verified"])

    def test_bounded_network_error_preserved_as_unknown(self):
        result=probe_one(FakeOpener(URLError("test connection unavailable")),
                         "en",ENDPOINTS[0][1])
        self.assertEqual(result["state"],"network_unavailable")
        self.assertIsNone(result["http_status"])
        self.assertFalse(result["get_form_verified"])

if __name__ == "__main__":
    unittest.main()
