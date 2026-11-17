"""New buyer-facing owner-held account disclosure: no checkout or legal acceptance."""
from dataclasses import FrozenInstanceError
import unittest

from prop_firm.plan1_buyer_no_social_amendment import current_plan1_buyer_copy
from prop_firm.plan1_owner_held_litefinance_policy import owner_held_real_account_policy
from prop_firm.plan1_owner_account_buyer_copy import (
    OLD_FA, OLD_EN, current_owner_account_buyer_copy,
)

class OwnerAccountBuyerCopyTests(unittest.TestCase):
    def setUp(self):
        self.c=current_owner_account_buyer_copy()

    def test_exact_real_challenge_sku(self):
        self.assertEqual(self.c.sku,"MOJ-PROP-01")

    def test_historical_version_preserved(self):
        self.assertEqual(self.c.historical_terms_version,"2026-11-15/v1.2")

    def test_old_signed_source_remains_unchanged(self):
        self.assertEqual(self.c.prior_no_social_demo_copy_digest_sha256,
                         current_plan1_buyer_copy().digest_sha256)

    def test_owner_account_amendment_digest_bound(self):
        self.assertEqual(self.c.owner_account_amendment_sha256,
                         owner_held_real_account_policy().digest_sha256)

    def test_owner_account_amendment_version_bound(self):
        self.assertEqual(self.c.owner_account_amendment_version,
                         owner_held_real_account_policy().amendment_version)

    def test_new_buyer_copy_digest_is_stable(self):
        self.assertEqual(self.c.digest_sha256,
                         current_owner_account_buyer_copy().digest_sha256)

    def test_new_copy_digest_not_old(self):
        self.assertNotEqual(self.c.digest_sha256,
                            current_plan1_buyer_copy().digest_sha256)

    def test_no_old_farsi_real_account_creation_promise(self):
        self.assertNotIn(OLD_FA,self.c.fa)

    def test_no_old_english_real_account_creation_promise(self):
        self.assertNotIn(OLD_EN,self.c.en)

    def test_owner_account_declared_in_farsi(self):
        self.assertIn("حساب واقعی موجود",self.c.fa)

    def test_litefinance_identified_in_english(self):
        self.assertIn("LiteFinance",self.c.en)

    def test_no_buyer_principal_transfer_in_farsi(self):
        self.assertIn("هیچ سرمایه‌ای",self.c.fa)

    def test_no_buyer_principal_transfer_in_english(self):
        self.assertIn("NO trading principal",self.c.en)

    def test_no_new_buyer_real_account_promise(self):
        self.assertFalse(self.c.new_buyer_broker_account_promised)

    def test_no_customer_funding_transfer(self):
        self.assertFalse(self.c.buyer_principal_transfer_enabled)

    def test_no_real_trading_authority_in_copy(self):
        self.assertFalse(self.c.live_owner_account_use_authorized_by_this_code)

    def test_no_buyer_contract_signature_claim(self):
        self.assertFalse(self.c.customer_acceptance_verified_by_this_code)

    def test_no_checkout_enabled(self):
        self.assertFalse(self.c.payment_enabled)

    def test_no_invoice_enabled(self):
        self.assertFalse(self.c.invoice_enabled)

    def test_no_payout_enabled(self):
        self.assertFalse(self.c.crypto_payout_enabled)

    def test_two_demo_stages_preserved(self):
        self.assertEqual(self.c.demo_stages,2)

    def test_28_day_evaluation_window_retained(self):
        self.assertIn("28-consecutive-day deadline",self.c.en)

    def test_50_closed_positions_retained(self):
        self.assertIn("50 distinct",self.c.en)

    def test_six_days_per_stage_retained(self):
        self.assertIn("6 verified trading days IN EACH stage",self.c.en)

    def test_30_native_trx_price_retained(self):
        self.assertIn("30 native TRX",self.c.en)

    def test_70_30_split_disclosed(self):
        self.assertIn("70% trader / 30% organizer",self.c.en)

    def test_14_levels_remain_conditional(self):
        self.assertIn("۱۴ سطح",self.c.fa)
        self.assertIn("conditional 14-level progression",self.c.en)

    def test_no_social_post_obligation_in_english(self):
        self.assertIn("NOT required",self.c.en)
        self.assertNotIn("ONE original Instagram and ONE original Facebook post",self.c.en)

    def test_no_social_post_obligation_in_farsi(self):
        self.assertIn("موظف",self.c.fa)
        self.assertNotIn("یک پست اصیل اینستاگرام",self.c.fa)

    def test_separate_crypto_payout_not_broker_withdrawal(self):
        self.assertIn("NOT a direct LiteFinance withdrawal",self.c.en)

    def test_broker_authorization_is_conditional(self):
        self.assertIn("explicitly permitted by the broker",self.c.en)

    def test_buyer_has_no_owner_credentials(self):
        self.assertIn("owner's credentials",self.c.en)

    def test_crypto_transfer_fee_disclosed(self):
        self.assertIn("deducted once",self.c.en)

    def test_fair_refunds_still_disclosed(self):
        self.assertIn("fair refunds",self.c.en)

    def test_buyer_copy_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.c.payment_enabled=True

    def test_information_only_status(self):
        self.assertIn("NEEDS_NEW_SIGNED_TERMS",self.c.status)
