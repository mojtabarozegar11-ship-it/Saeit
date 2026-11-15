"""C84 price-draft protection for the combined free/paid mojtaba.bot.ai funnel.

Synthetic reviewed leads only. No external communications, money or writes.
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from core.mojprop_offer_draft import build_offer_draft
from services.mojtaba_signal_catalog import get_signal_plan


def lead(notes, route="signals", consent=True, status="reviewing"):
    return SimpleNamespace(
        pk=19, status=status, consent=consent,
        request_id="MOJPROP-20261115-A1B2C3D4",
        name="Consent-based Buyer", email="buyer@example.com",
        route=route, notes=notes, get_horizon_display=lambda: "This week",
    )


def notes_for(code, amount=None):
    plan = get_signal_plan(code)
    price = format(plan.price_usd, ".2f") if amount is None else amount
    return (
        f"Requested educational plan: {code} (indicative USD {price}; written quote required)\n"
        "I request a human-reviewed, risk-disclosed historical gold-market briefing."
    )


class FreeAndPaidSignalPriceIntegrityTests(SimpleTestCase):
    def test_three_price_plans_use_authoritative_catalog(self):
        for code, price in (
            ("education-weekly", "9.90"),
            ("education-monthly", "29.90"),
            ("education-quarterly", "79.90"),
        ):
            with self.subTest(code=code):
                draft = build_offer_draft(lead(notes_for(code)))
                self.assertIn("Buyer-selected plan: " + code, draft)
                self.assertIn("indicative catalog amount USD " + price, draft)
                self.assertIn("final quote NOT APPROVED", draft)
                self.assertNotIn("Indicative starting amount: USD 29", draft)

    def test_missing_plan_does_not_invent_general_signal_price(self):
        draft = build_offer_draft(lead("Please prepare educational research with market risks and invalidation."))
        self.assertIn("Price WITHHELD: no specific educational signal plan selected", draft)
        self.assertNotIn("Indicative starting amount: USD 29", draft)

    def test_tampered_price_is_withheld_even_when_plan_code_is_known(self):
        for amount in ("0.01", "9.91", "99.00", "29.90"):
            with self.subTest(amount=amount):
                draft = build_offer_draft(lead(notes_for("education-weekly", amount)))
                self.assertIn("Price WITHHELD: inconsistent customer plan or amount", draft)
                self.assertNotIn("indicative catalog amount", draft)

    def test_injected_or_unknown_first_line_is_never_quoted(self):
        for first_line in (
            "Requested educational plan: education-lifetime (indicative USD 0.01; written quote required)",
            "Requested educational plan: education-weekly (indicative USD 9.90; invoice paid)",
            "Requested educational plan: education-quarterly (indicative USD 79.9; written quote required)",
            "Requested educational plan: education-weekly and education-monthly (indicative USD 9.90; written quote required)",
        ):
            with self.subTest(line=first_line):
                draft = build_offer_draft(lead(first_line + "\nHuman review of risk methodology required."))
                self.assertIn("Price WITHHELD:", draft)
                self.assertNotIn("indicative catalog amount", draft)

    def test_free_example_request_remains_nonfinancial(self):
        draft = build_offer_draft(lead(
            "Requested free educational example: one-off manual review; no paid subscription. "
            "Please show a dated hypothetical learning case and risk boundaries."
        ))
        self.assertIn("FREE educational example requested", draft)
        self.assertIn("no price quoted", draft)
        self.assertNotIn("indicative catalog amount", draft)

    def test_mixed_free_and_paid_scope_does_not_automatically_price(self):
        draft = build_offer_draft(lead(
            "Requested free educational example: explain historical risk, and discuss "
            "education-quarterly at some later review."
        ))
        self.assertIn("Price WITHHELD: conflicting free/paid", draft)
        self.assertNotIn("indicative catalog amount", draft)

    def test_noncanonical_single_code_in_notes_stays_nonbinding(self):
        draft = build_offer_draft(lead(
            "I'd like the education-weekly syllabus, with independent sources and no profit promise."
        ))
        self.assertIn("Buyer-selected plan: education-weekly", draft)
        self.assertIn("Plan identity must be confirmed", draft)

    def test_non_signal_routes_retain_specific_service_prices(self):
        for route, price in (("blueprint", "149"), ("brief", "39"), ("audit", "249")):
            with self.subTest(route=route):
                draft = build_offer_draft(lead(notes_for("education-weekly"), route=route))
                self.assertIn("Indicative starting amount: USD " + price, draft)

    def test_review_and_consent_remain_mandatory(self):
        for status, consent in (("new", True), ("reviewing", False), ("closed", True)):
            with self.subTest(status=status, consent=consent):
                with self.assertRaisesRegex(ValueError, "real_consent_and_operator_review_required"):
                    build_offer_draft(lead(notes_for("education-monthly"), status=status, consent=consent))

    def test_proposal_generation_has_no_email_money_or_customer_mutation(self):
        buyer = lead(notes_for("education-monthly"))
        snapshot = vars(buyer).copy()
        with patch("django.core.mail.send_mail", side_effect=AssertionError("no send")):
            draft = build_offer_draft(buyer)
        self.assertEqual(snapshot, vars(buyer))
        self.assertIn("UNSENT", draft)
        self.assertIn("Payment: DISABLED", draft)
