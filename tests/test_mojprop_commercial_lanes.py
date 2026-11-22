import unittest
from dataclasses import replace
from services.mojprop_commercial_lanes import LegalEvidence, Lane, PaymentMethod, NATIVE_TRX_SUN, decide_preinvoice

def evidence(**changes):
    base = LegalEvidence(True, "IR", True, "AE", True, True, True, True,
                         True, True, True, "COUNSEL-SIGNED-2026-123",
                         seller_role="natural_person_independent_service",
                         seller_role_verified=True,
                         iran_foreign_trx_settlement_lawfulness_reviewed=True,
                         us_person_and_us_nexus_excluded=True,
                         relevant_sanctions_screen_verified=True)
    return replace(base, **changes)

class CommercialLanesTests(unittest.TestCase):
    def test_recruitment_never_collects(self):
        for method in PaymentMethod:
            r = decide_preinvoice(Lane.RECRUITMENT, method, None)
            self.assertEqual(r.eligible_for_next_step, method is PaymentMethod.NONE)
            self.assertFalse(r.payable_invoice_issued)
            self.assertIsNone(r.proposed_native_sun)

    def test_domestic_no_trx(self):
        r = decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX,
                              evidence(buyer_residence_country="IR"))
        self.assertFalse(r.eligible_for_next_step)

    def test_domestic_fiat_quote_no_invoice(self):
        r = decide_preinvoice(Lane.EVALUATION, PaymentMethod.IRR,
                              evidence(buyer_residence_country="IR"))
        self.assertTrue(r.eligible_for_next_step)
        self.assertIsNone(r.proposed_native_sun)
        self.assertFalse(r.payable_invoice_issued)

    def test_missing_evidence_fails_closed(self):
        for missing in ("merchant_owner_verified", "buyer_residence_verified",
                        "customer_country_permitted", "fee_based_independent_evaluation_approved",
                        "seller_cross_border_lawful_basis_reviewed", "full_terms_accepted_and_verified",
                        "refunds_and_consumer_rights_cleared", "payment_method_legally_cleared",
                        "authorized_receiving_account_verified"):
            r = decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX,
                                  evidence(**{missing: False}))
            self.assertFalse(r.eligible_for_next_step, missing)
        self.assertFalse(decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX,
                                          None).eligible_for_next_step)

    def test_licensee_cannot_merchant_accept_trx(self):
        r = decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX,
                              evidence(seller_role="licensed_crypto_broker"))
        self.assertFalse(r.eligible_for_next_step)
        self.assertIn("art.38", r.reason)

    def test_unknown_or_fictitious_independent_seller_not_approved(self):
        for e in (evidence(seller_role="unknown"),
                  evidence(seller_role_verified=False),
                  evidence(seller_role="other")):
            self.assertFalse(decide_preinvoice(
                Lane.EVALUATION, PaymentMethod.NATIVE_TRX, e).eligible_for_next_step)

    def test_foreign_trx_and_sanctions_evidence_required(self):
        for missing in ("iran_foreign_trx_settlement_lawfulness_reviewed",
                        "us_person_and_us_nexus_excluded",
                        "relevant_sanctions_screen_verified"):
            decision = decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX,
                                         evidence(**{missing: False}))
            self.assertFalse(decision.eligible_for_next_step, missing)

    def test_qualified_foreign_quote_no_receipt(self):
        r = decide_preinvoice(Lane.EVALUATION, PaymentMethod.NATIVE_TRX, evidence())
        self.assertTrue(r.eligible_for_next_step)
        self.assertEqual(r.proposed_native_sun, NATIVE_TRX_SUN)
        self.assertFalse(r.payable_invoice_issued)
        self.assertFalse(r.challenge_access_granted)
        self.assertFalse(r.revenue_recognized)

    def test_invalid_country_and_counsel_reference(self):
        for bad in (evidence(buyer_residence_country="iran"),
                    evidence(merchant_residence_country=""),
                    evidence(compliance_reference="unproven")):
            self.assertFalse(decide_preinvoice(Lane.EVALUATION,
                PaymentMethod.NATIVE_TRX, bad).eligible_for_next_step)

if __name__ == "__main__":
    unittest.main()
