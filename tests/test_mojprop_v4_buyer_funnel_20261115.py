"""Contract for the real customer-facing static Moj Prop landing page.

This test never pretends a response was paid or delivered.
"""
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class MojPropV4ConversionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (
            Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html"
        ).read_text("utf-8")

    def test_all_customer_choices_are_actual_intake_codes(self):
        for service in ("blueprint", "signals", "brief", "audit"):
            self.assertIn(f'<option value="{service}">', self.html)
        for horizon in ("urgent", "week", "month", "review"):
            self.assertIn(f'<option value="{horizon}">', self.html)

    def test_signal_links_preserve_the_requested_service(self):
        self.assertIn("new URLSearchParams(window.location.search).get('service')", self.html)
        self.assertIn("document.getElementById('service').value=requestedService", self.html)
        self.assertIn("Object.prototype.hasOwnProperty.call(labels,requestedService)", self.html)

    def test_no_phantom_receipt_without_confirmed_server_id(self):
        self.assertIn("response.status!==201", self.html)
        self.assertIn("typeof data.request_id!=='string'", self.html)
        self.assertIn("MOJPROP-[0-9]{8}-[A-F0-9]{8}", self.html)
        self.assertIn("copy.disabled=true", self.html)
        self.assertNotIn("Math.random().toString(36)", self.html)

    def test_bounded_and_recoverable_submission(self):
        self.assertIn("new AbortController()", self.html)
        self.assertIn("setTimeout(()=>abortController.abort(),15000)", self.html)
        self.assertIn("if(response.status===403) csrfToken=''", self.html)
        self.assertIn("clearTimeout(timeout)", self.html)
        self.assertIn("X-CSRFToken", self.html)

    def test_frontend_matches_backend_constraints(self):
        for attr in ('minlength="2"', 'maxlength="200"', 'maxlength="254"',
                     'minlength="20"', 'maxlength="5000"'):
            self.assertIn(attr, self.html)
        self.assertIn('id="website" name="website"', self.html)
        self.assertIn('id="consent"', self.html)
        self.assertIn('aria-live="polite"', self.html)

    def test_no_wallet_or_guaranteed_profit_path(self):
        self.assertIn("No payment was taken.", self.html)
        self.assertIn("This form sends a request", self.html)
        self.assertNotIn("localStorage.setItem('mojprop-last-request'", self.html)
