"""Contract gate is observational and fail-closed for new gold buyers."""
import unittest
from prop_firm.xauusd_v13_contract_gate import audit_v13_gold_terms
from prop_firm.xauusd_v13_preflight import DRAFT_CONTRACT_VERSION
from prop_firm.order_readiness import TERMS_VERSION, assess_plan_one, REQUIRED
from prop_firm.rules import POLICY
from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy

class NewBuyerGoldTermsTests(unittest.TestCase):
    def test_old_contract_unchanged(self):
        self.assertEqual(TERMS_VERSION,"2026-11-15/v1.2")
        self.assertEqual(POLICY.version,TERMS_VERSION)

    def test_new_contract_unique(self):
        self.assertNotEqual(DRAFT_CONTRACT_VERSION,TERMS_VERSION)

    def test_fifty_trade_conflict_is_explicit_blocker(self):
        d=audit_v13_gold_terms()
        self.assertIn("fifty_trades_per_phase_vs_combined_conflict",d.blockers)

    def test_new_contract_cannot_claim_signed_terms(self):
        self.assertFalse(audit_v13_gold_terms().approved_bilingual_terms_signed)

    def test_new_contract_not_in_historical_intake(self):
        self.assertFalse(audit_v13_gold_terms().contract_version_propagated_to_intake)

    def test_new_contract_not_payable(self):
        d=audit_v13_gold_terms()
        self.assertFalse(d.public_checkout_allowed)
        self.assertFalse(d.invoice_allowed)
        self.assertFalse(d.customer_enrollment_allowed)

    def test_new_contract_cannot_enable_real_orders(self):
        self.assertFalse(audit_v13_gold_terms().live_trading_allowed)

    def test_new_contract_no_independent_capital_broker_proof(self):
        d=audit_v13_gold_terms()
        self.assertFalse(d.independently_verified_capital)
        self.assertFalse(d.independently_verified_broker_account)

    def test_social_posts_waived_in_current_copy(self):
        v=current_plan1_buyer_copy()
        self.assertEqual(v.instagram_posts_required,0)
        self.assertEqual(v.facebook_posts_required,0)

    def test_old_order_review_rejects_new_draft_terms(self):
        evidence={name:True for name in REQUIRED}
        d=assess_plan_one(evidence,contract_version=DRAFT_CONTRACT_VERSION)
        self.assertFalse(d.eligible)
        self.assertIn("versioned_contract",d.missing)

    def test_old_order_readiness_does_not_enable_checkout(self):
        self.assertFalse(POLICY.trx_checkout_enabled)
        self.assertFalse(POLICY.real_orders_enabled)

    def test_legal_release_remains_absent(self):
        self.assertIn("v13_independent_legal_release_unverified",
                      audit_v13_gold_terms().blockers)

if __name__=="__main__":
    unittest.main()
