"""Actual public static form ↔ existing Django contract (no database or network)."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "templates/moj-prop-v4/index.html"
BACKEND = ROOT / "core/mojprop_views.py"


class Form(HTMLParser):
    def __init__(self):
        super().__init__()
        self.select = None
        self.options = {}
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.select = attrs.get("id")
            self.options[self.select] = []
        elif tag == "option" and self.select:
            self.options[self.select].append(attrs.get("value"))
        if tag in ("input", "textarea") and attrs.get("id"):
            self.fields[attrs["id"]] = attrs

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None


class CanonicalPublicMojPropContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = PUBLIC.read_text(encoding="utf-8")
        cls.backend = BACKEND.read_text(encoding="utf-8")
        cls.form = Form()
        cls.form.feed(cls.html)

    def test_horizon_codes_match_actual_django_choices(self):
        self.assertEqual(self.form.options["horizon"], [
            "urgent", "week", "month", "review",
        ])
        for code in self.form.options["horizon"]:
            self.assertIn('("' + code + '", ', (ROOT / "core/models.py").read_text())

    def test_never_submit_horizon_as_label(self):
        self.assertNotIn(None, self.form.options["horizon"])
        self.assertNotIn("This week", self.form.options["horizon"])

    def test_service_routes_match_actual_django_choices(self):
        self.assertEqual(
            set(self.form.options["service"]),
            {"blueprint", "signals", "brief", "audit"},
        )

    def test_exact_canonical_request_url(self):
        self.assertIn("const endpoint='/moj-prop-intake/';", self.html)

    def test_guest_email_mandatory_and_bounded(self):
        email = self.form.fields["email"]
        self.assertIn("required", email)
        self.assertEqual(email["type"], "email")
        self.assertEqual(email["maxlength"], "254")

    def test_request_name_has_backend_minimum(self):
        name = self.form.fields["name"]
        self.assertIn("required", name)
        self.assertEqual(name["minlength"], "2")
        self.assertEqual(name["maxlength"], "200")

    def test_request_notes_have_backend_limits(self):
        note = self.form.fields["notes"]
        self.assertIn("required", note)
        self.assertEqual(note["minlength"], "20")
        self.assertEqual(note["maxlength"], "5000")

    def test_consent_is_explicit_and_required(self):
        self.assertIn("required", self.form.fields["consent"])
        self.assertIn("I consent to storing my contact details and request notes", self.html)
        self.assertIn("not an order, payment, funded account or profit promise", self.html)

    def test_validity_checked_before_fetch(self):
        self.assertIn("if(!form.reportValidity()) return;", self.html)
        self.assertIn("credentials:'same-origin'", self.html)
        self.assertIn("'X-CSRFToken':token", self.html)

    def test_public_page_does_not_claim_unverified_live_desk(self):
        self.assertNotIn("DESK ONLINE", self.html)

    def test_success_is_manual_review_not_payment(self):
        self.assertIn("received for manual review", self.html)
        self.assertIn("No payment was taken.", self.html)

    def test_honeypot_retained_without_visitor_display(self):
        self.assertEqual(self.form.fields["website"].get("name"), "website")
        self.assertEqual(self.form.fields["website"].get("aria-hidden"), "true")


if __name__ == "__main__":
    unittest.main()
