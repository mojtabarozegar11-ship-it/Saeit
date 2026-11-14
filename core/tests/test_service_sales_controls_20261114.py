"""No-IO regressions for real deliverables and non-automated commercial gates."""
from unittest import TestCase

from core.service_sales_controls import (
    REQUIRED_OFFER_EVIDENCE, SERVICE_CARDS, assess_service_offer,
    list_service_cards, service_card,
)


def evidence(value=True):
    return {key: value for key in REQUIRED_OFFER_EVIDENCE}


class ServiceSalesTests(TestCase):
    def test_six_services_have_unique_codes(self):
        self.assertEqual(len(list_service_cards()), 6)
        self.assertEqual(len({r["service_code"] for r in list_service_cards()}), 6)

    def test_research_services_are_present(self):
        self.assertTrue({"AGR-01", "RS-01", "RS-02", "RS-03"} <= set(SERVICE_CARDS))

    def test_commercial_web_services_present(self):
        self.assertTrue({"WEB-01", "SEO-01"} <= set(SERVICE_CARDS))

    def test_research_catalogue_has_full_deliverables(self):
        for card in list_service_cards():
            self.assertGreaterEqual(len(card["deliverables"]), 4)
            self.assertTrue(card["limitation"])
            self.assertTrue(card["customer"])

    def test_all_products_have_no_approved_price_claim(self):
        for card in list_service_cards():
            self.assertIsNone(card["price"])
            self.assertFalse(card["external_sale_enabled"])

    def test_original_cards_cannot_be_mutated_globally(self):
        original = service_card("AGR-01")["title_fa"]
        copy = service_card("AGR-01")
        copy["title_fa"] = "tampered"
        self.assertEqual(service_card("AGR-01")["title_fa"], original)

    def test_static_catalogue_top_level_is_immutable(self):
        with self.assertRaises(TypeError):
            SERVICE_CARDS["HACK"] = {}

    def test_static_catalogue_inner_is_immutable(self):
        with self.assertRaises(TypeError):
            SERVICE_CARDS["RS-02"]["title_fa"] = "tampered"

    def test_unknown_service_code_rejected(self):
        with self.assertRaises(ValueError):
            service_card("NO-SUCH-SERVICE")

    def test_lowercase_service_code_rejected(self):
        with self.assertRaises(ValueError):
            service_card("rs-01")

    def test_non_string_service_code_rejected(self):
        with self.assertRaises(ValueError):
            service_card(None)

    def test_all_true_only_allows_internal_review(self):
        result = assess_service_offer("AGR-01", evidence())
        self.assertTrue(result["internal_review_ready"])
        self.assertFalse(result["external_sale_enabled"])
        self.assertIsNone(result["live_settlement"])
        self.assertIsNone(result["live_delivery"])

    def test_unknown_evidence_prevents_ready(self):
        result = assess_service_offer("RS-01", evidence(None))
        self.assertEqual(result["unknown"], len(REQUIRED_OFFER_EVIDENCE))
        self.assertEqual(result["passed"], 0)
        self.assertFalse(result["internal_review_ready"])

    def test_failed_evidence_prevents_ready(self):
        result = assess_service_offer("RS-02", evidence(False))
        self.assertEqual(result["failed"], len(REQUIRED_OFFER_EVIDENCE))
        self.assertFalse(result["internal_review_ready"])

    def test_only_pricing_failure_blocks(self):
        gates = evidence()
        gates["pricing_costed_and_owner_approved"] = False
        result = assess_service_offer("WEB-01", gates)
        self.assertFalse(result["internal_review_ready"])
        self.assertEqual(result["passed"], len(gates)-1)
        self.assertEqual(result["failed"], 1)

    def test_only_payment_unavailable_blocks(self):
        gates = evidence()
        gates["payment_method_legally_available"] = None
        self.assertFalse(assess_service_offer("RS-03", gates)["internal_review_ready"])

    def test_only_delivery_unverified_blocks(self):
        gates = evidence()
        gates["delivery_method_verified"] = False
        self.assertFalse(assess_service_offer("SEO-01", gates)["internal_review_ready"])

    def test_unknown_key_does_not_bypass_review(self):
        values = evidence()
        values["auto_activate_live_sales"] = True
        with self.assertRaises(ValueError):
            assess_service_offer("AGR-01", values)

    def test_missing_gate_rejected(self):
        values = evidence()
        del values["data_rights_and_privacy_cleared"]
        with self.assertRaises(ValueError):
            assess_service_offer("AGR-01", values)

    def test_wrong_evidence_object_rejected(self):
        with self.assertRaises(ValueError):
            assess_service_offer("AGR-01", [True] * len(REQUIRED_OFFER_EVIDENCE))

    def test_string_true_does_not_bypass(self):
        values = evidence()
        values["contract_and_legal_basis_approved"] = "true"
        with self.assertRaises(ValueError):
            assess_service_offer("AGR-01", values)

    def test_integer_one_does_not_bypass(self):
        values = evidence()
        values["contract_and_legal_basis_approved"] = 1
        with self.assertRaises(ValueError):
            assess_service_offer("AGR-01", values)

    def test_percentage_denominator_is_all_gates(self):
        gates = evidence(None)
        gates[REQUIRED_OFFER_EVIDENCE[0]] = True
        r = assess_service_offer("AGR-01", gates)
        self.assertEqual(r["source_evidence_percentage"], 12.5)
        self.assertEqual(r["total"], 8)

    def test_always_retain_financial_approval(self):
        r = assess_service_offer("AGR-01", evidence())
        self.assertTrue(r["final_external_commitment_requires_separate_approval"])

    def test_code_list_never_contains_customer_data(self):
        text = repr(list_service_cards())
        self.assertNotIn("customer@example", text)
        self.assertNotIn("payment_intent", text)
