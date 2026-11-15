"""Public-facing receipt follow-up must remain a private bearer-token lookup."""
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse
from core.mojprop_views import mojprop_receipt_status


class MojPropReceiptFrontendContract(SimpleTestCase):
    def html(self):
        return (Path(settings.BASE_DIR) / "templates/moj-prop-v4/index.html").read_text("utf-8")

    def test_public_form_includes_safe_privately_exportable_receipt(self):
        html = self.html()
        for required in ("id=\"receipt-token\"", "id=\"status-check\"",
                         "id=\"status-result\"", "data.receipt_token",
                         "Private receipt token (keep secret):"):
            self.assertIn(required, html)
        self.assertNotIn("localStorage.setItem", html)
        self.assertNotIn("sessionStorage.setItem", html)

    def test_bearer_lookup_is_read_only_and_never_sends_contact_pii(self):
        html = self.html()
        self.assertIn("method:'POST',credentials:'same-origin',cache:'no-store'", html)
        self.assertIn("'X-CSRFToken':csrfValue", html)
        self.assertIn("body:JSON.stringify({receipt_token:receiptToken})", html)
        self.assertIn("const statusEndpoint='/moj-prop-status/'", html)
        self.assertNotIn("'/moj-prop-status/?receipt_token='", html)
        self.assertNotIn("localStorage.setItem('receipt_token'", html)
        self.assertEqual(reverse("mojprop_receipt_status"), "/moj-prop-status/")
        self.assertIs(resolve("/moj-prop-status/").func, mojprop_receipt_status)

    def test_receipt_download_is_explicit_user_action_with_local_blob(self):
        html = self.html()
        for required in (
            'id="download" disabled', "download.addEventListener('click'",
            "if(!receipt) return", "new Blob([receipt+", "URL.createObjectURL(blob)",
            "a.download=filename", "a.click()", "URL.revokeObjectURL(uri)",
        ):
            self.assertIn(required, html)
        self.assertNotIn("localStorage.setItem", html)
        self.assertNotIn("sessionStorage.setItem", html)

    def test_manual_receipt_has_distinct_names_for_accepted_and_unsent_drafts(self):
        html = self.html()
        self.assertIn("Request ID: (MOJPROP-[A-Z0-9-]+)", html)
        self.assertIn("matched[1].toLowerCase()+'-private.txt'", html)
        self.assertIn("'mojprop-unsent-draft.txt'", html)
        self.assertIn("Private receipt token (keep secret):", html)

    def test_browser_input_limits_match_actual_customer_intake_boundaries(self):
        html = self.html()
        self.assertIn('id="name" required minlength="2" maxlength="200"', html)
        self.assertIn('id="email" type="email" required maxlength="254"', html)
        self.assertIn('id="notes" required minlength="20" maxlength="5000"', html)
        self.assertIn('id="website" name="website" maxlength="120"', html)
        self.assertIn('id="consent" type="checkbox" required', html)

    def test_retry_does_not_offer_stale_receipt_as_current_submission(self):
        html = self.html()
        self.assertIn("copy.disabled=true;", html)
        self.assertIn("download.disabled=true;", html)
        self.assertIn("receipt='';", html)
        self.assertIn("The token shown belongs to a previous saved request", html)
        self.assertIn("form.setAttribute('aria-busy','true')", html)
        self.assertIn("form.removeAttribute('aria-busy')", html)

    def test_failed_intake_explains_field_errors_without_creating_fake_receipt(self):
        html = self.html()
        self.assertIn("Object.entries(data.fields)", html)
        self.assertIn("response.status===429", html)
        self.assertIn("This submission was not accepted.", html)
        self.assertNotIn("not submitted; local draft only", html)
        self.assertIn("receipt='';", html)
        self.assertIn("copy.disabled=true;", html)
        self.assertIn("download.disabled=true;", html)
        # User-triggered local download stays supported for a server-backed
        # receipt; a failed POST may not unlock it or mint a phantom sale.
        self.assertIn("download.addEventListener('click'", html)
        self.assertIn("Copy unavailable — use Save private receipt", html)

    def test_financial_brand_signal_link_prefills_the_actual_service_code(self):
        html = self.html()
        self.assertIn("new URLSearchParams(window.location.search).get('service')", html)
        self.assertIn("Object.prototype.hasOwnProperty.call(labels,requestedService)", html)
        self.assertIn("serviceSelect.value=requestedService", html)
        self.assertNotIn("eval(requestedService)", html)
        self.assertIn("<option value=\"signals\">Educational signals", html)
        self.assertIn("const labels={", html)

    def test_referral_query_is_not_interpolated_into_html_or_executed(self):
        html = self.html()
        self.assertNotIn("innerHTML=selectedRoute", html)
        self.assertNotIn("eval(selectedRoute)", html)
        self.assertNotIn("document.write(selectedRoute)", html)
        self.assertNotIn("window.location.href=selectedRoute", html)
