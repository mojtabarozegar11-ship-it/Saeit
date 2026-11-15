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
