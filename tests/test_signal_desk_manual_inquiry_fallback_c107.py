"""C107: signal free email 404 must not strand the independent manual lead.

This is a source-only safety regression. It never POSTs a real signup/email,
collects payment, issues a quote, or claims the live site is updated.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIGNAL_HTML = ROOT / "templates/moj-prop-v4/signals/index.html"
INTAKE_MODULE = ROOT / "core/mojprop_accessible_intake.py"


class SignalDeskManualLeadFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = SIGNAL_HTML.read_text(encoding="utf-8")
        cls.form = INTAKE_MODULE.read_text(encoding="utf-8")

    def test_01_manual_independent_request_is_a_real_link(self):
        self.assertIn('href="/moj-prop-intake/?format=html"', self.page)

    def test_02_fallback_is_visible_without_javascript(self):
        self.assertIn('id="manual-research-fallback"', self.page)
        pre_script = self.page.split("<script>", 1)[0]
        self.assertIn('id="manual-research-fallback"', pre_script)

    def test_03_educational_signal_route_is_customer_selectable(self):
        self.assertIn('name="service"', self.form)
        self.assertIn('MojPropRequest.ROUTE_CHOICES', self.form)
        self.assertIn('if value !=', self.form)
        catalog = (ROOT / "core/mojprop_catalog_contract.py").read_text(encoding="utf-8")
        self.assertIn('PublicMojPropService("signals"', catalog)

    def test_04_manual_lead_uses_csrf_protected_post(self):
        self.assertIn('name="csrfmiddlewaretoken"', self.form)
        self.assertIn('method="post"', self.form)
        self.assertIn('name="consent"', self.form)
        self.assertIn('name="idempotency_key"', self.form)

    def test_05_no_js_fallback_does_not_send_subscription_email(self):
        self.assertIn("does not subscribe you", self.page)
        self.assertIn("No mailing membership has been created", self.page)
        self.assertNotIn('href="/moj-signal-free-subscribe/"', self.page)

    def test_06_failed_free_signup_stays_disabled_without_server_readiness(self):
        self.assertIn("submit.disabled=!enabled", self.page)
        self.assertIn("body.enabled===true", self.page)
        self.assertIn("r.status!==202", self.page)

    def test_07_no_fake_paid_entitlement_on_lead(self):
        self.assertIn("does not subscribe you, issue an invoice, collect money", self.page)
        self.assertIn("No payment, live account or return is promised.", self.form)

    def test_08_exact_root_wsgi_path_matches_live_django_url(self):
        routes = (ROOT / "config/urls.py").read_text(encoding="utf-8")
        self.assertIn('path("moj-prop-intake/"', routes)
        self.assertIn('"/moj-prop-intake/?format=html"', self.form)

    def test_09_buyer_contact_form_checks_email_and_purpose(self):
        self.assertIn('name="email"', self.form)
        self.assertIn('name="notes"', self.form)
        self.assertIn('name="horizon"', self.form)

    def test_10_no_redirect_to_unowned_bot_dns_host(self):
        self.assertNotIn('href="https://mojtaba.bot.ai', self.page)
        self.assertNotIn('action="https://mojtaba.bot.ai', self.page)


if __name__ == "__main__":
    unittest.main()
