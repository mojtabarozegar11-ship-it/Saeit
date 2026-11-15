"""Protect the ACTUAL static public Moj Prop form from 400-only conversion bugs."""
from html.parser import HTMLParser
from pathlib import Path
from django.test import SimpleTestCase
from core.models import MojPropRequest

PAGE=Path(__file__).resolve().parents[1]/"templates/moj-prop-v4/index.html"


class IntakeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.select=None
        self.options={}
        self.inputs={}
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=="select":
            self.select=attrs.get("id")
            self.options.setdefault(self.select,[])
        if tag=="option" and self.select:
            self.options[self.select].append(attrs.get("value"))
        if tag in ("input","textarea") and attrs.get("id"):
            self.inputs[attrs["id"]]=attrs
    def handle_endtag(self,tag):
        if tag=="select":
            self.select=None


class MojPropCommercialFormParityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html=PAGE.read_text(encoding="utf-8")
        cls.parsed=IntakeParser()
        cls.parsed.feed(cls.html)

    def test_horizon_options_are_backend_codes_not_human_labels(self):
        self.assertEqual(set(self.parsed.options["horizon"]),
                         {key for key,_ in MojPropRequest.HORIZON_CHOICES})

    def test_service_routes_match_django_model_exactly(self):
        self.assertEqual(set(self.parsed.options["service"]),
                         {key for key,_ in MojPropRequest.ROUTE_CHOICES})

    def test_horizon_cannot_send_default_label_text(self):
        self.assertNotIn(None,self.parsed.options["horizon"])
        self.assertNotIn("Today / urgent",self.parsed.options["horizon"])

    def test_name_has_actual_backend_minimum_length(self):
        self.assertEqual(self.parsed.inputs["name"]["minlength"],"2")
        self.assertEqual(self.parsed.inputs["name"]["maxlength"],"200")

    def test_notes_minlength_matches_backend_requirement(self):
        self.assertEqual(self.parsed.inputs["notes"]["minlength"],"20")
        self.assertEqual(self.parsed.inputs["notes"]["maxlength"],"5000")

    def test_email_required_for_contact_and_length_bounded(self):
        self.assertIn("required",self.parsed.inputs["email"])
        self.assertEqual(self.parsed.inputs["email"]["type"],"email")
        self.assertEqual(self.parsed.inputs["email"]["maxlength"],"254")

    def test_explicit_private_contact_storage_consent_required(self):
        self.assertIn("required",self.parsed.inputs["consent"])
        self.assertIn("I consent to storing my name, email, and request notes",self.html)

    def test_form_posts_one_canonical_backend_route_only(self):
        self.assertIn("const endpoint='/moj-prop-intake/';",self.html)
        self.assertNotIn("const endpoint='/moj-prop/intake/';",self.html)

    def test_csrf_and_same_origin_are_used_for_post(self):
        self.assertIn("'X-CSRFToken':token",self.html)
        self.assertIn("credentials:'same-origin'",self.html)

    def test_no_unverified_online_claim(self):
        self.assertNotIn("DESK ONLINE",self.html)
        self.assertIn("SERVICE VERIFY PENDING",self.html)

    def test_honeypot_field_remains_present(self):
        self.assertEqual(self.parsed.inputs["website"].get("name"),"website")

    def test_offer_is_manual_and_not_an_auto_payment(self):
        self.assertIn("No payment was taken.",self.html)
        self.assertNotIn("data-payment-confirmed",self.html)
