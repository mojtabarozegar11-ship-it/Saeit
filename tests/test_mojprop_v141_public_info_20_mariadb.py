"""Actual Django GET/HEAD of 20-language MOJ-PROP-01 public draft pages.

Read-only, no identity collection, payment, checkout, or production deploy.
"""
from django.test import TestCase, override_settings
from django.utils.html import escape
from prop_firm.moj_prop_page import SUPPORTED_CODES
from prop_firm.mojprop_v141_info_i18n import info_catalog
from prop_firm.mojprop_v141_interest_i18n import interest_catalog
from prop_firm.models import PropV141Interest, PropAccount, PropChallengeEnrollment

HOST = "mojplaywin.com"
PATH = "/moj-prop-v141-info/"


@override_settings(
    ALLOWED_HOSTS=[HOST, "www.mojplaywin.com", "zomorodmelal.ir"],
    MOJ_PROP_V141_INTEREST_ENABLED=True,
)
class LocalizedPublicInfoTests(TestCase):
    def test_all_20_codes_exact_and_canonical(self):
        self.assertEqual(len(SUPPORTED_CODES), 20)
        self.assertEqual(set(info_catalog()), set(SUPPORTED_CODES))
        self.assertEqual(set(interest_catalog()), set(SUPPORTED_CODES))

    def test_twenty_real_http_pages_are_fully_localized_and_read_only(self):
        for code in SUPPORTED_CODES:
            with self.subTest(code=code):
                page = self.client.get(
                    PATH + "?lang=" + code, HTTP_HOST=HOST, secure=True,
                )
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, 'lang="' + code + '" dir="' +
                                    interest_catalog()[code]["dir"] + '"')
                self.assertContains(page, escape(info_catalog()[code]["heading"]))
                for key in ("overview", "risk", "social", "funding", "legal"):
                    self.assertContains(page, escape(info_catalog()[code][key]))
                self.assertContains(page, 'href="/moj-prop-v141-interest/?lang=' + code + '"')
                self.assertIn("no-store", page["Cache-Control"])
                self.assertIn("frame-ancestors 'none'", page["Content-Security-Policy"])
                self.assertEqual(page.content.count(b'<form'), 0)
                for target in SUPPORTED_CODES:
                    self.assertContains(page, 'href="/moj-prop-v141-info/?lang=' + target + '"')
        self.assertEqual(PropV141Interest.objects.count(), 0)
        self.assertEqual(PropAccount.objects.count(), 0)
        self.assertEqual(PropChallengeEnrollment.objects.count(), 0)

    def test_baseline_bilingual_proposed_terms_unmodified_and_nonpayable(self):
        page = self.client.get(PATH, secure=True, HTTP_HOST=HOST)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'v1.4.1-50-OR-28D-DRAFT')
        self.assertContains(page, 'NOT OPEN FOR PAID ENROLLMENT')
        self.assertContains(page, 'href="mailto:mojplaywin@gmail.com')
        self.assertEqual(PropV141Interest.objects.count(), 0)

    def test_disable_interest_hides_localized_form_cta_not_information(self):
        with override_settings(MOJ_PROP_V141_INTEREST_ENABLED=False):
            page = self.client.get(PATH + "?lang=ur", secure=True, HTTP_HOST=HOST)
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, escape(info_catalog()["ur"]["legal"]))
            self.assertNotContains(page, 'href="/moj-prop-v141-interest/?lang=ur"')

    def test_bad_query_and_wrong_host_404_or_non_mutating_method(self):
        for suffix in ("?lang=xx", "?lang=en&lang=fa", "?email=a", "?lang=en&amount=30"):
            with self.subTest(suffix=suffix):
                self.assertEqual(self.client.get(
                    PATH + suffix, secure=True, HTTP_HOST=HOST).status_code, 404)
        self.assertEqual(self.client.get(PATH + "?lang=ar", secure=False,
                                         HTTP_HOST=HOST).status_code, 404)
        self.assertEqual(self.client.get(PATH + "?lang=ar", secure=True,
                                         HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.post(PATH + "?lang=ar", secure=True,
                                          HTTP_HOST=HOST).status_code, 405)
        self.assertEqual(PropV141Interest.objects.count(), 0)

    def test_head_has_headers_but_zero_body(self):
        result = self.client.head(PATH + "?lang=zh", secure=True, HTTP_HOST=HOST)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"")
        self.assertIn("no-store", result["Cache-Control"])
