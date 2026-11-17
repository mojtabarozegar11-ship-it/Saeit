"""Production-reality guard for MOJ-PROP-01 PRELAUNCH contact, not paid checkout.

The external site's canonical Plan1 form and private receipt status were HTTP
404 on 17-18 November. This static page must route visitors to a KNOWN live
first-party support contact until a separate approved production release.
"""
import re
from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "templates/moj-prop-v4/index.html"


class _Elements(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchor_urls = []
        self.forms = {}
        self.current = None

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == "a":
            self.anchor_urls.append((attrs.get("href", ""), attrs))
        if tag == "form":
            self.current = attrs.get("id", "")
            self.forms[self.current] = attrs

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


class LiveContactFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")
        cls.dom = _Elements()
        cls.dom.feed(cls.text)
        cls.dom.close()

    def test_01_explicitly_the_real_prop_product_not_starter30(self):
        self.assertIn("SOLE CURRENT PRODUCT · MOJ-PROP-01", self.text)
        self.assertNotIn("MOJPROP-STARTER30", self.text)
        self.assertNotIn("starter-30-trx", self.text)

    def test_02_no_known_dead_plan1_consent_get_links(self):
        self.assertFalse(any(
            href.startswith("/moj-prop-interest/form/")
            for href, _ in self.dom.anchor_urls))

    def test_03_supported_first_party_contact_is_primary_cta(self):
        paths = [href for href, _ in self.dom.anchor_urls]
        self.assertGreaterEqual(paths.count("/moj-prop/contact/"), 8)
        self.assertIn('class="btn primary" href="/moj-prop/contact/"', self.text)

    def test_04_farsi_contact_is_real_page_not_unlaunched_form(self):
        self.assertIn("صفحه تماس رسمی برای اطلاعات پلن ۱ مج پراپ", self.text)
        self.assertIn("تماس رسمی برای دریافت شرایط کتبی پلن ۱", self.text)

    def test_05_payment_is_not_live_and_broker_access_not_promised(self):
        self.assertIn("no paid challenge", self.text.lower())
        self.assertIn("no payment", self.text.lower())
        self.assertIn("legal", self.text.lower())
        self.assertNotIn("tronweb.trx.sendtransaction", self.text.lower())

    def test_06_receipt_status_control_is_hidden_until_live_proven(self):
        attrs = self.dom.forms.get("status-form")
        self.assertIsNotNone(attrs)
        self.assertIn("hidden", attrs)
        self.assertEqual(attrs.get("aria-hidden"), "true")
        self.assertEqual(attrs.get("style"), "display:none")
        self.assertIn("Receipt status lookup is not yet live", self.text)

    def test_07_user_is_told_to_keep_private_token_off_email(self):
        self.assertIn("Never send the token by email", self.text)
        self.assertIn("Keep any private receipt token offline", self.text)

    def test_08_no_broken_accessible_html_route_invited(self):
        self.assertFalse(any(
            href.startswith("/moj-prop-intake/?format=html")
            for href, _ in self.dom.anchor_urls))

    def test_09_demonstrates_28_day_single_challenge_window(self):
        self.assertIn("28 calendar days", self.text)
        self.assertIn("9.6%", self.text)
        self.assertIn("6%", self.text)
        self.assertIn("50", self.text)

    def test_10_promises_no_automatic_email_campaign_from_contact(self):
        self.assertIn("No automated promotional email", self.text)
        self.assertIn("voluntary request", self.text.lower())

    def test_11_does_not_call_support_a_verified_crm_lead(self):
        self.assertIn("not validated CRM opt-ins", self.text)
        self.assertIn("do not assume a submitted request was saved", self.text)

    def test_12_preserves_secure_legacy_intake_for_other_services(self):
        self.assertIn("const endpoint='/moj-prop-intake/'", self.text)
        self.assertIn("JSON.stringify(", self.text)
        self.assertIn("credentials:'same-origin'", self.text)


if __name__ == "__main__":
    unittest.main()
