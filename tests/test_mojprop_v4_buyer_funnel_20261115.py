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
        self.assertIn("response.status===201 && data.reused!==true", self.html)
        self.assertIn("response.status===200 && data.reused===true", self.html)
        self.assertIn("typeof data.request_id!=='string'", self.html)
        self.assertIn("ID-[A-F0-9]{24}", self.html)
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

    def test_manual_product_selection_for_direct_site_visitors(self):
        """A digital buyer without prefilled URL must be able to pick a SKU."""
        self.assertIn('id="digital-product" name="digital-product"', self.html)
        self.assertIn('id="digital-product-field" hidden', self.html)
        for sku in ("72", "225", "879"):
            self.assertIn('<option value="'+sku+'">', self.html)
        self.assertIn("serviceSelector.addEventListener('change',syncDigitalProduct)",self.html)
        self.assertIn("productSelector.required=isDigital",self.html)
        self.assertIn("productSelector.disabled=!isDigital",self.html)
        self.assertIn("product_id:selectedProduct",self.html)
        self.assertIn("Catalog product ID: '+(selectedProduct||'n/a')",self.html)

    def test_server_request_timeout_covers_csrf_and_post(self):
        self.assertIn("async function csrf(signal)",self.html)
        self.assertIn("cache:'no-store',signal",self.html)
        self.assertIn("await csrf(abortController.signal)",self.html)
        self.assertIn("signal:abortController.signal",self.html)

    def test_customer_research_plan_is_kept_in_confirmed_crm_submission(self):
        for plan in ("education-weekly", "education-monthly", "education-quarterly"):
            self.assertIn("'"+plan+"'", self.html)
        self.assertIn(".get('plan')", self.html)
        self.assertIn("Object.prototype.hasOwnProperty.call(signalPlans,requestedPlan)", self.html)
        self.assertIn("A recurring subscription and payment have not been authorized.", self.html)
        self.assertIn("const payload={name,email,service,horizon,notes:submittedNotes,website,", self.html)
        self.assertIn("body:JSON.stringify({...payload,idempotency_key:pendingSubmission.key})", self.html)
        self.assertIn("Requested educational plan: ", self.html)
        self.assertIn("selected-signal-plan", self.html)

    def test_funded_plan1_contact_never_reuses_educational_billing_identity(self):
        self.assertNotIn('href="/moj-prop-interest/form/"', self.html)
        self.assertNotIn('href="/moj-prop-interest/form/?lang=fa"', self.html)
        self.assertIn("MOJ-PROP-01", self.html)
        self.assertIn("Dedicated Plan 1 form not live", self.html)
        self.assertNotIn("MOJPROP-STARTER30", self.html)
        self.assertNotIn('href="/moj-prop-intake/?format=html"', self.html)
        self.assertIn("form not live", self.html.lower())
        self.assertNotIn("tronweb.trx.sendtransaction", self.html.lower())

    def test_no_wallet_or_guaranteed_profit_path(self):
        self.assertIn("No payment was taken.", self.html)
        self.assertIn("request form and private receipt lookup have NOT been independently verified in production", self.html)
        self.assertIn("do not assume a submitted request was saved", self.html)
        self.assertNotIn("localStorage.setItem('mojprop-last-request'", self.html)
