import unittest
from decimal import Decimal as D

from prop_firm.synthetic_sale import (
    SyntheticSaleOffer, assess_synthetic_sale,
)


class SyntheticSaleTests(unittest.TestCase):
    def test_offer_is_publicly_describable(self):
        offer = SyntheticSaleOffer()
        self.assertEqual(offer.sku, "MOJ-PROP-SIM-01")
        self.assertEqual(offer.entry_fee_trx, 30)
        self.assertEqual(offer.retry_fee_trx, 18)
        self.assertEqual(offer.challenge_days, 60)
        self.assertEqual(offer.data_mode, "synthetic_replay")
        self.assertFalse(offer.virtual_principal_withdrawable)
        self.assertFalse(offer.customer_deposit_required)
        self.assertEqual(offer.reward_reserve_pct_of_settled_fee, 80)
        self.assertTrue(offer.maximum_reward_is_settled_reserve)
        self.assertEqual(offer.public_disclosure()["account_mode"], "simulated")

    def test_default_decision_is_fail_closed(self):
        result = assess_synthetic_sale(
            reward_reserve_available_usd=0,
            maximum_reward_commitment_usd=50,
            terms_disclosed=False,
            reserve_policy_accepted=False,
            recipient_configured=True,
            activation_approved=False,
        )
        self.assertFalse(result.eligible_for_activation)
        self.assertFalse(result.checkout_enabled)
        self.assertEqual(len(result.blockers), 4)

    def test_reserve_shortfall_blocks_activation(self):
        result = assess_synthetic_sale(
            reward_reserve_available_usd=49.99,
            maximum_reward_commitment_usd=50,
            terms_disclosed=True,
            reserve_policy_accepted=True,
            recipient_configured=True,
            activation_approved=True,
        )
        self.assertIn("reward_reserve_shortfall", result.blockers)

    def test_full_evidence_allows_activation_decision(self):
        result = assess_synthetic_sale(
            reward_reserve_available_usd=50,
            maximum_reward_commitment_usd=50,
            terms_disclosed=True,
            reserve_policy_accepted=True,
            recipient_configured=True,
            activation_approved=True,
        )
        self.assertTrue(result.eligible_for_activation)
        self.assertTrue(result.checkout_enabled)
        self.assertEqual(result.blockers, ())

    def test_no_customer_deposit_and_no_virtual_principal(self):
        offer = SyntheticSaleOffer()
        self.assertFalse(offer.customer_deposit_required)
        self.assertFalse(offer.virtual_principal_withdrawable)

    def test_reward_cap_policy_cannot_drift(self):
        with self.assertRaises(ValueError):
            SyntheticSaleOffer(reward_reserve_pct_of_settled_fee=70)
        with self.assertRaises(ValueError):
            SyntheticSaleOffer(maximum_reward_is_settled_reserve=False)

    def test_retry_price_and_discount_are_fixed(self):
        offer = SyntheticSaleOffer()
        self.assertEqual(offer.retry_fee_trx, 18)
        self.assertEqual(offer.retry_discount_pct, 40)


if __name__ == "__main__":
    unittest.main()
