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
        self.assertIn("credentials:'omit'", html)
        self.assertIn("referrerPolicy:'no-referrer'", html)
        self.assertIn("cache:'no-store'", html)
        self.assertIn("encodeURIComponent(token)", html)
        self.assertIn("'/moj-prop-status/?receipt_token='", html)
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

    def test_failed_intake_explains_field_errors_and_supports_offline_draft(self):
        html = self.html()
        self.assertIn("Object.entries(data.fields)", html)
        self.assertIn("response.status===429", html)
        self.assertIn("not submitted; local draft only", html)
        self.assertIn("download.disabled=false;", html)
        self.assertIn("Copy unavailable — use Save private receipt", html)
