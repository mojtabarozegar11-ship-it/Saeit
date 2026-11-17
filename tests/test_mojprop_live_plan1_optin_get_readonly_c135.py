"""C135 synthetic public GET diagnosis, no actual browser customer request."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.mojprop_live_plan1_optin_get_readonly_c135 import (
    ENDPOINTS, MAX_HTML, assess, FormGetEvidence, NoRedirect
)

HEADERS = {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "private, no-store, max-age=0",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def template(lang="en"):
    direction = "rtl" if lang == "fa" else "ltr"
    return (f'<!doctype html><html lang="{lang}" dir="{direction}">'
            '<body><form method="post" action="/moj-prop-interest/">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="secret-never-logged">'
            '<input type="hidden" name="plan_code" value="MOJ-PROP-01">'
            '<input type="hidden" name="consent_version" value="moj-prop-interest-v1">'
            f'<input type="hidden" name="source_language" value="{lang}">'
            '<input type="email" name="email">'
            '<input type="checkbox" name="contact_consent" value="yes">'
            '</form></body></html>').encode("utf-8")


def proof(lang="en", **kwargs):
    kwargs.setdefault("status", 200)
    kwargs.setdefault("requested_url", ENDPOINTS[lang.upper()])
    kwargs.setdefault("final_url", ENDPOINTS[lang.upper()])
    kwargs.setdefault("headers", dict(HEADERS))
    kwargs.setdefault("body", template(lang))
    kwargs.setdefault("lang", lang)
    return assess(**kwargs)


class Plan1PublicGetC135Tests(unittest.TestCase):
    def test_only_two_fixed_first_party_https_urls(self):
        self.assertEqual(set(ENDPOINTS), {"EN", "FA"})
        self.assertEqual(ENDPOINTS["EN"], "https://mojplaywin.com/moj-prop-interest/form/")
        self.assertEqual(ENDPOINTS["FA"], ENDPOINTS["EN"] + "?lang=fa")

    def test_real_django_form_shape_is_accepted_synthetically(self):
        for lang in ("en", "fa"):
            with self.subTest(lang=lang):
                result = proof(lang)
                self.assertTrue(result.valid_public_get)
                self.assertTrue(result.csrf_and_consent_form)

    def test_not_found_is_not_a_lead_or_valid_form(self):
        result = proof(status=404, body=b"Not Found")
        self.assertFalse(result.valid_public_get)
        self.assertFalse(result.csrf_and_consent_form)
        self.assertEqual(result.status, 404)

    def test_redirect_never_counts_as_public_form(self):
        result = proof(status=302, final_url="https://other.invalid/login", body=b"")
        self.assertFalse(result.no_redirect)
        self.assertFalse(result.valid_public_get)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://other.invalid"))

    def test_generic_html_200_never_counts_as_consent(self):
        result = proof(body=b'<html><title>Something else</title></html>')
        self.assertTrue(result.typed_html)
        self.assertFalse(result.csrf_and_consent_form)
        self.assertFalse(result.valid_public_get)

    def test_form_must_bind_exact_post_and_real_plan(self):
        cases = (
            ('action="/moj-prop-interest/"', 'action="/moj-prop-intake/"'),
            ('value="MOJ-PROP-01"', 'value="MOJPROP-STARTER30"'),
            ('name="contact_consent"', 'name="marketing_consent"'),
            ('name="csrfmiddlewaretoken"', 'name="missing_csrf"'),
            ('value="moj-prop-interest-v1"', 'value="v0"'),
            ('method="post"', 'method="get"'),
            ('type="checkbox"', 'type="hidden"'),
        )
        for needle, replacement in cases:
            with self.subTest(changed=needle):
                self.assertFalse(proof(body=template().replace(
                    needle.encode(), replacement.encode()
                )).valid_public_get)

    def test_language_and_source_language_must_match(self):
        self.assertFalse(proof("fa", body=template("en")).valid_public_get)
        self.assertFalse(proof("fa", body=template("fa").replace(
            b'lang="fa"', b'lang="en"', 1
        )).valid_public_get)
        self.assertFalse(proof("fa", body=template("fa").replace(
            b' dir="rtl"', b' dir="ltr"', 1
        )).valid_public_get)

    def test_security_headers_required(self):
        for field in ("Cache-Control", "X-Frame-Options", "Content-Security-Policy"):
            with self.subTest(field=field):
                bad = dict(HEADERS)
                del bad[field]
                self.assertFalse(proof(headers=bad).valid_public_get)

    def test_external_action_or_double_form_rejected(self):
        html = template()
        self.assertFalse(proof(body=html.replace(b'action="/moj-prop-interest/"',
                                                 b'action="https://attacker.invalid/"')).valid_public_get)
        self.assertFalse(proof(body=html.replace(b"</body>",
                                                 b'<form method="post"></form></body>')).valid_public_get)

    def test_oversized_and_invalid_encoding_are_rejected(self):
        self.assertFalse(proof(body=b"a" * (MAX_HTML+1)).valid_public_get)
        self.assertFalse(proof(body=b"\xff\xfe").valid_public_get)

    def test_form_status_independent_from_paid_or_customer_post(self):
        src = (Path(__file__).resolve().parents[1] /
               "scripts/mojprop_live_plan1_optin_get_readonly_c135.py").read_text("utf-8")
        for needed in ("MOJPROP_C135_REAL_BUYER_POST_VERIFIED=false",
                       "MOJPROP_C135_PAYMENT_OR_ENROLLMENT=false",
                       "MOJPROP_C135_LIVE_RELEASE_AUTHORIZED=false"):
            self.assertIn(needed, src)
        self.assertNotIn("requests.post(", src)
        self.assertNotIn("send_mail(", src)
        self.assertNotIn("objects.create(", src)


if __name__ == "__main__":
    unittest.main()
