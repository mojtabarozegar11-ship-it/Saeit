"""C131 integration: canonical PropInterest backend + static Plan1 funnel.

Source-only and synthetic anti-redirect tests: no network, user data, customer
POST, payment, broker, deployment or migration execution.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import subprocess
import sys

from scripts.mojprop_plan1_form_source_gate_c130 import (
    FORM, _canonical_links, _source_routes, _view_guards, evaluate, KEYS
)

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "templates/moj-prop-v4/index.html"
CONTACT = ROOT / "templates/moj-prop/contact/index.html"
RUNNER = ROOT / "scripts/mojprop_plan1_form_source_gate_c130.py"
CANON_URLS = ROOT / "config/urls.py"
CANON_VIEWS = ROOT / "core/moj_prop_views.py"
FORM_TEMPLATE = ROOT / "core/templates/mojplaywin/moj_prop_interest_form_d.html"

VALID = ('<html><a href="/moj-prop-interest/form/">EN</a>'
         '<a href="/moj-prop-interest/form/?lang=fa">FA</a></html>')


class CanonicalPlan1IntegrationTests(TestCase):
    def test_static_and_django_backend_now_share_source_branch(self):
        proof = evaluate(ROOT)
        self.assertEqual(tuple(proof.keys()), KEYS)
        self.assertTrue(all(proof.values()), proof)

    def test_get_post_urls_resolve_to_distinct_canonical_views_in_source(self):
        get, post = _source_routes(CANON_URLS.read_text("utf-8"))
        self.assertTrue(get)
        self.assertTrue(post)
        self.assertTrue(_view_guards(CANON_VIEWS.read_text("utf-8")))
        self.assertNotEqual(FORM, "/moj-prop-intake/")

    def test_both_pages_offer_english_and_rtl_farsi_canonical_optin(self):
        for page in (CONTACT, LANDING):
            with self.subTest(page=page.name):
                text = page.read_text("utf-8")
                self.assertTrue(_canonical_links(text))
                self.assertIn('href="/moj-prop-interest/form/"', text)
                self.assertIn('href="/moj-prop-interest/form/?lang=fa"', text)
                self.assertNotIn('/moj-prop-interest/form/?service=', text)

    def test_no_plan1_blueprint_cta_remains_in_funded_landing(self):
        text = LANDING.read_text("utf-8")
        self.assertNotIn('href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=moj-prop-01"', text)
        self.assertIn("Other service requests — not Plan 1", text)
        self.assertIn("const endpoint='/moj-prop-intake/'", text)
        self.assertIn("MOJ-PROP-01", text)
        self.assertNotIn("MOJPROP-STARTER30", text)

    def test_plan1_contact_is_safely_nonpayable(self):
        page = CONTACT.read_text("utf-8")
        self.assertIn("no payment details or private credentials", page)
        self.assertIn("nothing is sent automatically", page)
        self.assertNotIn("<form", page)
        self.assertNotIn("<script", page)
        self.assertIn("not a verified Plan 1 lead", " ".join(page.replace("<strong>","").replace("</strong>","").split()).lower())

    def test_private_consent_form_uses_actual_post_and_csrf(self):
        template = FORM_TEMPLATE.read_text("utf-8")
        self.assertIn('action="/moj-prop-interest/"', template)
        self.assertIn("{% csrf_token %}", template)
        self.assertIn('name="contact_consent"', template)
        self.assertIn('name="plan_code" value="MOJ-PROP-01"', template)
        self.assertNotIn('action="/moj-prop-intake/', template)
        self.assertNotIn('name="wallet"', template)

    def test_release_source_pass_alone_has_no_live_or_payment_proof(self):
        p = subprocess.run(
            [sys.executable, str(RUNNER), "--require-source-ready"],
            cwd=ROOT, check=False, capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("MOJPROP_C130_SOURCE_READY=true", p.stdout)
        for marker in (
            "MOJPROP_C130_LIVE_PASSENGER_PARITY_PROVEN=false",
            "MOJPROP_C130_CONSENTED_BUYER_POST_VERIFIED=false",
            "MOJPROP_C130_PAYMENT_OR_DEPLOYMENT=false",
        ):
            self.assertIn(marker, p.stdout)
        self.assertNotIn("support@mojplaywin.com", p.stdout)

    def test_mismatched_or_duplicate_parameter_is_denied(self):
        for suffix in (
            "?service=blueprint&package=moj-prop-01",
            "?lang=fa&package=moj-prop-01",
            "?lang=fa&lang=fa",
            "?lang=en",
            "?lang=fa#payment",
            "?email=customer@example.test",
            "?lang=fa&receipt_token=guess",
            "?lang=fa&wallet=guess",
            "?lang=fa&free=1",
            "?lang=fa&lang=en",
            "?lang=FA",
            "?lang=",
        ):
            with self.subTest(suffix=suffix):
                self.assertFalse(_canonical_links(VALID.replace(
                    FORM + "?lang=fa", FORM + suffix
                )))

    def test_external_and_non_canonical_links_denied(self):
        for prefix in (
            "//other.example", "https://other.example", "https://mojplaywin.com",
            "http://mojplaywin.com",
        ):
            with self.subTest(prefix=prefix):
                self.assertFalse(_canonical_links(VALID.replace(
                    'href="/moj-prop-interest/form/"',
                    f'href="{prefix}/moj-prop-interest/form/"'
                )))

    def test_truncated_or_unexpected_candidate_count_denied(self):
        self.assertFalse(_canonical_links("<html></html>"))
        self.assertFalse(_canonical_links(VALID.replace("lang=fa", "lang=en")))
        self.assertFalse(_canonical_links(VALID.replace("?lang=fa", "")))
        self.assertFalse(_canonical_links(VALID * 12))

    def test_tampered_canonical_get_route_is_denied(self):
        source = CANON_URLS.read_text("utf-8")
        old = 'path("moj-prop-interest/form/", moj_prop_interest_form'
        self.assertIn(old, source)
        self.assertFalse(_source_routes(source.replace(old, 'path("moj-prop-interest/form/", moj_prop_interest'))[0])

    def test_tampered_canonical_post_route_is_denied(self):
        source = CANON_URLS.read_text("utf-8")
        old = 'path("moj-prop-interest/", moj_prop_interest'
        self.assertIn(old, source)
        self.assertFalse(_source_routes(source.replace(old, 'path("moj-prop-interest/", moj_prop_interest_form'))[1])

    def test_view_drops_csrf_or_post_guard_fails_closed(self):
        source = CANON_VIEWS.read_text("utf-8")
        self.assertTrue(_view_guards(source))
        self.assertFalse(_view_guards(source.replace("@require_POST", "@missing_POST")))
        self.assertFalse(_view_guards(source.replace("@csrf_protect", "@missing_csrf")))

    def test_missing_consent_migration_blocks_source_evidence(self):
        root=ROOT
        migrated = root / "prop_firm/migrations/0008_prospect_contact_intake.py"
        with patch("scripts.mojprop_plan1_form_source_gate_c130._read") as mocked:
            actual = __import__("scripts.mojprop_plan1_form_source_gate_c130", fromlist=["_read"])._read
            # This override simulates only the missing migration.
            def read(root, relative):
                if relative == "prop_firm/migrations/0008_prospect_contact_intake.py":
                    return ""
                return actual(root, relative)
            mocked.side_effect=read
            self.assertFalse(evaluate(root)["source_ready"])

    def test_no_network_or_payment_code_in_source_gate(self):
        src = RUNNER.read_text("utf-8")
        for forbidden in ("requests.post(", "requests.get(", "urllib.request",
                          "smtplib", "wallet_transfer", "deploy_host",
                          "objects.create(", "SECRET_KEY"):
            self.assertNotIn(forbidden, src)

    def test_original_30_trx_offer_not_educational_deposit(self):
        page=LANDING.read_text("utf-8")
        self.assertIn("30 native TRX", page)
        self.assertIn("30,000,000 SUN", page)
        self.assertIn("NOT an educational product", page)
        self.assertIn("No wallet or payment collection now.", page)


if __name__ == "__main__":
    import unittest
    unittest.main()
