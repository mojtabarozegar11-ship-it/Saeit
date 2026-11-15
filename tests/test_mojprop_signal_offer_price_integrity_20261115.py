"""C84: offer-draft price must never contradict the canonical single-bot plans.

These tests use only unsaved synthetic lead objects. No DB write, external
contact, payment, trade, subscription or deployment takes place.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core.mojprop_offer_draft import build_offer_draft
from services.mojtaba_signal_catalog import get_signal_plan


def lead_for(route="signals", notes=None, status="reviewing", consent=True):
    if notes is None:
        notes = "Customer seeks independent educational scenarios for gold markets."
    return SimpleNamespace(
        pk=123,
        request_id="MOJPROP-20261115-A1B2C3D4",
        route=route,
        status=status,
        consent=consent,
        name="Demo Customer",
        email="buyer@example.com",
        notes=notes,
        get_horizon_display=lambda: "This week",
    )


def plan_notes(plan_id, price=None):
    plan = get_signal_plan(plan_id)
    amount = format(plan.price_usd, "f") if price is None else price
    return (
        f"Requested educational plan: {plan_id} "
        f"(indicative USD {amount}; written quote required)\n"
        "Please deliver independent, risk-disclosed learning materials on gold."
    )


class SignalDraftPriceIntegrityTests(SimpleTestCase):
    def test_all_three_canonical_plans_are_buyer_preferences_not_invoices(self):
        for name, expected in (
            ("education-weekly", "9.90"),
            ("education-monthly", "29.90"),
            ("education-quarterly", "79.90"),
        ):
            with self.subTest(plan=name):
                output = build_offer_draft(lead_for(notes=plan_notes(name)))
                self.assertIn("Buyer-requested plan (NOT independently verified): " + name, output)
                self.assertIn("catalog reference USD " + expected, output)
                self.assertIn("independent owner approval", output)
                self.assertIn("NOT AN INVOICE OR SUBSCRIPTION", output)
                self.assertNotIn("Indicative starting amount: USD 29", output)

    def test_no_plan_does_not_fabricate_a_generic_signal_price(self):
        output = build_offer_draft(lead_for())
        self.assertIn("Educational signal plan: NOT SELECTED", output)
        self.assertNotIn("Indicative starting amount: USD 29", output)
        self.assertNotIn("catalog reference USD", output)

    def test_tampered_claimed_price_cannot_generate_a_quote(self):
        for tampered in ("0.01", "99.00", "9.91", "29.90"):
            if tampered == "9.90":
                continue
            with self.subTest(amount=tampered):
                with self.assertRaisesRegex(ValueError, "price_does_not_match"):
                    build_offer_draft(lead_for(notes=plan_notes("education-weekly", tampered)))

    def test_unrecognized_or_injected_plan_cannot_generate_a_quote(self):
        for line in (
            "Requested educational plan: education-lifetime (indicative USD 0.01; written quote required)",
            "Requested educational plan: education-weekly;DROP TABLE requests (indicative USD 9.90; written quote required)",
            "Requested educational plan: education-weekly (indicative USD 9.90; payment approved)",
            "Requested educational plan: education-monthly (indicative USD 29.9; written quote required)",
        ):
            with self.subTest(line=line):
                with self.assertRaisesRegex(ValueError, "invalid_customer_signal_plan_attribution"):
                    build_offer_draft(lead_for(notes=line + "\nNormal learning request."))

    def test_valid_plan_prefix_below_first_line_is_not_pricing_authority(self):
        notes = "Please offer a general market briefing.\n" + plan_notes("education-quarterly")
        draft = build_offer_draft(lead_for(notes=notes))
        self.assertIn("Educational signal plan: NOT SELECTED", draft)
        self.assertNotIn("catalog reference USD 79.90", draft)

    def test_non_signals_keep_existing_catalog_pricing(self):
        for route, expected in (("blueprint", "149"), ("brief", "39"), ("audit", "249")):
            with self.subTest(route=route):
                draft = build_offer_draft(lead_for(route=route, notes=plan_notes("education-weekly")))
                self.assertIn("Indicative starting amount: USD " + expected, draft)
                self.assertNotIn("catalog reference USD", draft)

    def test_unreviewed_or_unconsented_customer_never_gets_offer(self):
        for status, consent in (("new", True), ("reviewing", False), ("closed", True)):
            with self.subTest(status=status, consent=consent):
                with self.assertRaisesRegex(ValueError, "real_consent_and_operator_review_required"):
                    build_offer_draft(lead_for(status=status, consent=consent, notes=plan_notes("education-weekly")))

    def test_drafting_is_pure_and_does_not_contact_or_mutate_customer(self):
        customer = lead_for(notes=plan_notes("education-monthly"))
        prior = vars(customer).copy()
        with patch("django.core.mail.send_mail", side_effect=AssertionError("no email permitted")):
            draft = build_offer_draft(customer)
        self.assertEqual(vars(customer), prior)
        self.assertIn("UNSENT", draft)
        self.assertIn("Payment: DISABLED", draft)


if __name__ == "__main__":
    import unittest
    unittest.main()
