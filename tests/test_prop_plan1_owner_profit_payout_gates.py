"""Reconciled real profit -> separate treasury crypto payout is NEVER automatic."""
from dataclasses import FrozenInstanceError
import unittest
from prop_firm.plan1_owner_profit_payout_gates import (
    REQUIRED_PROFIT_PAYOUT_PROOFS, review_private_profit_payout_proofs,
)

class CompanyAccountProfitPayoutGateTests(unittest.TestCase):
    def all_flags(self):
        return dict.fromkeys(REQUIRED_PROFIT_PAYOUT_PROOFS,True)

    def test_exact_eighteen_payout_evidence_slots(self):
        self.assertEqual(len(REQUIRED_PROFIT_PAYOUT_PROOFS),18)

    def test_missing_all_evidence_denied(self):
        with self.assertRaises(ValueError):
            review_private_profit_payout_proofs(evidence={})

    def test_bad_evidence_type_denied(self):
        with self.assertRaises(ValueError):
            review_private_profit_payout_proofs(evidence=None)

    def test_extra_fake_approval_denied(self):
        flags=self.all_flags()
        flags["autorun_broker_withdrawal"]=True
        with self.assertRaises(ValueError):
            review_private_profit_payout_proofs(evidence=flags)

    def test_every_missing_evidence_blocks_independently(self):
        for proof in REQUIRED_PROFIT_PAYOUT_PROOFS:
            with self.subTest(proof=proof):
                flags=self.all_flags()
                flags[proof]=False
                result=review_private_profit_payout_proofs(evidence=flags)
                self.assertFalse(result.eligible_for_independent_payout_finance_review)
                self.assertIn(proof,result.missing)

    def test_truthy_integer_is_never_crypto_authorization(self):
        flags=self.all_flags()
        flags["beneficiary_wallet_ownership_and_network_verified"]=1
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_unverified_profit_statement_blocks(self):
        flags=self.all_flags()
        flags["complete_realized_profit_broker_statement_reconciled"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_unrealized_floating_pnl_blocks(self):
        flags=self.all_flags()
        flags["unrealized_pnl_excluded"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_broker_permission_required_independently(self):
        flags=self.all_flags()
        flags["broker_third_party_trading_permission_in_force"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_loss_carryforward_cannot_be_ignored(self):
        flags=self.all_flags()
        flags["negative_prior_period_loss_carryforward_reconciled"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_double_pay_of_same_positions_blocks(self):
        flags=self.all_flags()
        flags["no_prior_payment_of_same_period_or_positions"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_unclear_buyer_contract_period_blocks(self):
        flags=self.all_flags()
        flags["settlement_period_and_profit_70_30_signed_by_buyer"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_no_source_compliant_broker_withdrawal_blocks(self):
        flags=self.all_flags()
        flags["company_broker_withdrawal_obeys_original_source_rules"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_no_available_company_treasury_blocks(self):
        flags=self.all_flags()
        flags["company_treasury_funds_independently_available"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_beneficiary_kyc_and_sanctions_required(self):
        flags=self.all_flags()
        flags["payout_legality_and_beneficiary_kyc_sanctions_verified"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_unverified_buyer_wallet_blocks(self):
        flags=self.all_flags()
        flags["beneficiary_wallet_ownership_and_network_verified"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_actual_transfer_fee_must_be_disclosed(self):
        flags=self.all_flags()
        flags["actual_transfer_network_fee_pre_disclosed_and_verified"]=False
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=flags).eligible_for_independent_payout_finance_review)

    def test_all_proofs_even_if_synthetic_never_pay_directly(self):
        result=review_private_profit_payout_proofs(evidence=self.all_flags())
        self.assertTrue(result.eligible_for_independent_payout_finance_review)
        self.assertFalse(result.crypto_transfer_authorized)
        self.assertFalse(result.transfer_broadcast)
        self.assertFalse(result.transaction_confirmed)

    def test_all_proofs_never_approve_broker_withdrawal(self):
        result=review_private_profit_payout_proofs(evidence=self.all_flags())
        self.assertFalse(result.broker_withdrawal_authorized)

    def test_all_proofs_never_claim_verified_legal_ownership(self):
        result=review_private_profit_payout_proofs(evidence=self.all_flags())
        self.assertFalse(result.owner_account_verified_by_this_module)
        self.assertFalse(result.broker_delegation_authorized_by_this_module)
        self.assertFalse(result.beneficiary_identity_verified_by_this_module)

    def test_result_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            review_private_profit_payout_proofs(
                evidence=self.all_flags()).crypto_transfer_authorized=True

    def test_no_fictional_accounts_payable_liability_created(self):
        self.assertFalse(review_private_profit_payout_proofs(
            evidence=self.all_flags()).trader_profit_liability_created)
