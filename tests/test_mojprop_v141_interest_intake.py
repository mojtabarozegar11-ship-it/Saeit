"""Real Django HTTP/database checks for isolated v1.4.1 contact-only funnel.

All paths are default-OFF in production. These tests create disposable rows
only; they must not call a broker, settle TRX, email or enroll a customer.
"""
from urllib.parse import urlencode
from pathlib import Path
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings

from prop_firm.models import (
    PropAccount, PropChallengeEnrollment, PropInterest, PropV141Interest,
)
from prop_firm.plan1_v141_lead_models import CONSENT_VERSION

PATH = "/moj-prop-v141-interest/"
HOST = "mojplaywin.com"
VALID = {
    "email": "Buyer@farmco.org",
    "plan_code": "MOJ-PROP-01",
    "consent_version": CONSENT_VERSION,
    "contact_consent": "yes",
    "language": "en",
}


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"],
    MOJ_PROP_V141_INTEREST_ENABLED=True,
)
class V141LeadIntakeTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, data=None, client=None, secure=True, host=HOST, path=PATH):
        body = urlencode(VALID if data is None else data)
        return (client or self.client).post(
            path, data=body, content_type="application/x-www-form-urlencoded",
            secure=secure, HTTP_HOST=host,
            HTTP_REFERER=("https://" if secure else "http://") + host + PATH,
        )

    def test_flag_off_blocks_get_and_post_with_no_database_write(self):
        with override_settings(MOJ_PROP_V141_INTEREST_ENABLED=False):
            self.assertEqual(self.client.get(PATH, secure=True,
                                              HTTP_HOST=HOST).status_code, 404)
            self.assertEqual(self.post().status_code, 404)
        self.assertFalse(PropV141Interest.objects.exists())

    def test_get_rendered_is_bilingual_no_store_and_owner_domain(self):
        for lang in ("en", "fa"):
            with self.subTest(lang=lang):
                response = self.client.get(
                    PATH + "?lang=" + lang, secure=True, HTTP_HOST=HOST)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="contact_consent"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, 'value="MOJ-PROP-01"')
                self.assertContains(response, CONSENT_VERSION)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("Cookie", response.get("Vary", ""))
                self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
                if lang == "fa":
                    self.assertContains(response, 'dir="rtl"')
                else:
                    self.assertContains(response, 'dir="ltr"')

    def test_head_sends_no_form_body(self):
        response = self.client.head(PATH, secure=True, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(PropV141Interest.objects.count(), 0)

    def test_one_real_consent_row_without_financial_side_effects(self):
        response = self.post()
        self.assertEqual(response.status_code, 202)
        lead = PropV141Interest.objects.get()
        self.assertEqual(lead.email, "buyer@farmco.org")
        self.assertEqual(lead.plan_code, "MOJ-PROP-01")
        self.assertEqual(lead.consent_version, CONSENT_VERSION)
        self.assertEqual(lead.status, "new")
        self.assertEqual(lead.source_language, "en")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(PropInterest.objects.count(), 0)
        self.assertEqual(PropAccount.objects.count(), 0)
        self.assertEqual(PropChallengeEnrollment.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_preserves_original_language_and_consent(self):
        self.assertEqual(self.post().status_code, 202)
        self.assertEqual(self.post(dict(VALID, language="fa")).status_code, 202)
        lead = PropV141Interest.objects.get()
        self.assertEqual(lead.source_language, "en")
        self.assertEqual(lead.consent_version, CONSENT_VERSION)
        self.assertEqual(PropV141Interest.objects.count(), 1)

    def test_opted_out_address_is_not_reactivated(self):
        self.assertEqual(self.post().status_code, 202)
        lead = PropV141Interest.objects.get()
        lead.status = "withdrawn"
        lead.save(update_fields=["status"])
        self.assertEqual(self.post().status_code, 202)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")
        lead.status = "new"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["status"])
        lead.refresh_from_db()
        self.assertEqual(lead.status, "withdrawn")

    def test_immutable_consent_origin_and_no_bulk_promotion(self):
        self.post()
        lead = PropV141Interest.objects.get()
        lead.email = "different@farmco.org"
        with self.assertRaises(ValidationError):
            lead.save(update_fields=["email"])
        with self.assertRaises(ValidationError):
            PropV141Interest.objects.all().update(email="other@farmco.org")
        with self.assertRaises(ValidationError):
            PropV141Interest.objects.all().update(status="contacted")
        self.assertEqual(PropV141Interest.objects.get().email, "buyer@farmco.org")

    def test_no_implicit_acceptance_of_other_product_or_terms(self):
        for field, value in (
            ("plan_code", "MOJPROP-STARTER30"),
            ("plan_code", "MOJ-PROP-02"),
            ("consent_version", "moj-prop-interest-v1"),
            ("contact_consent", "no"),
            ("contact_consent", ""),
            ("email", "invalid-address"),
            ("language", "ar"),
        ):
            with self.subTest(field=field, value=value):
                self.assertEqual(
                    self.post(dict(VALID, **{field: value})).status_code, 400)
        self.assertFalse(PropV141Interest.objects.exists())

    def test_https_host_scope_and_query_integrity(self):
        self.assertEqual(self.post(secure=False).status_code, 404)
        self.assertEqual(self.post(host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.post(path=PATH + "?email=a").status_code, 400)
        self.assertEqual(
            self.client.get(PATH + "?token=xxx", secure=True,
                            HTTP_HOST=HOST).status_code, 400)
        self.assertFalse(PropV141Interest.objects.exists())

    def test_csrf_prevents_external_guest_posts(self):
        guarded = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client=guarded).status_code, 403)
        self.assertFalse(PropV141Interest.objects.exists())
        form = guarded.get(PATH, secure=True, HTTP_HOST=HOST)
        self.assertEqual(form.status_code, 200)
        token = guarded.cookies["csrftoken"].value
        result = self.post(
            data={**VALID, "csrfmiddlewaretoken": token}, client=guarded)
        self.assertEqual(result.status_code, 202)
        self.assertEqual(PropV141Interest.objects.count(), 1)

    def test_duplicate_and_extra_field_rejected_without_lead(self):
        variants = (
            list(VALID.items()) + [("email", "other@farmco.org")],
            list(VALID.items()) + [("is_paid", "yes")],
            list(VALID.items()) + [("consent_version", CONSENT_VERSION)],
        )
        for data in variants:
            with self.subTest(data=data[-1]):
                self.assertEqual(self.post(data).status_code, 400)
        self.assertFalse(PropV141Interest.objects.exists())

    def test_rate_limit_is_fail_closed(self):
        for _ in range(8):
            self.assertEqual(self.post().status_code, 202)
        self.assertEqual(self.post().status_code, 429)
        self.assertEqual(PropV141Interest.objects.count(), 1)

    def test_unsupported_method_does_not_create_lead(self):
        response = self.client.put(PATH, secure=True, HTTP_HOST=HOST)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(PropV141Interest.objects.exists())

    def test_admin_uses_superuser_only_and_cannot_add_delete(self):
        # Isolated database CI does not install core or Django admin.
        source = (Path(__file__).resolve().parents[1] / "prop_firm/admin.py").read_text("utf-8")
        self.assertIn("@admin.register(PropV141Interest)", source)
        self.assertIn("class PropV141InterestAdmin(PropInterestAdmin)", source)
        self.assertIn("def has_add_permission", source)
        self.assertIn("def has_delete_permission", source)
