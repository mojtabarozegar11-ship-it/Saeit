"""Plan1: two simulated phases need NO real broker account, real only after pass.

Synthetic gating checks only: zero real account creation, zero financial side effects.
"""
from dataclasses import FrozenInstanceError
import unittest

from prop_firm.plan1_phase_account_boundary import (
    DEMO_STAGES, REAL_STAGE, REQUIRED_REAL_ACCOUNT_PROOFS,
    phase_account_boundary, review_demo_to_real_transition,
)


class DemoToRealBoundaryTests(unittest.TestCase):
    def all_evidence(self):
        return dict.fromkeys(REQUIRED_REAL_ACCOUNT_PROOFS, True)

    def test_demo_phase_one_is_simulated(self):
        self.assertTrue(phase_account_boundary().phase_one_simulated)

    def test_demo_phase_two_is_simulated(self):
        self.assertTrue(phase_account_boundary().phase_two_simulated)

    def test_both_demo_phases_named_without_real(self):
        self.assertEqual(DEMO_STAGES, ("phase_one", "phase_two"))

    def test_real_phase_is_separate(self):
        self.assertEqual(REAL_STAGE, "funded")

    def test_real_broker_account_not_needed_before_first_challenge(self):
        self.assertFalse(phase_account_boundary().real_account_required_to_start_phase_one)

    def test_real_broker_account_not_needed_before_second_challenge(self):
        self.assertFalse(phase_account_boundary().real_account_required_to_start_phase_two)

    def test_broker_live_kyc_not_needed_for_demo_account_as_such(self):
        self.assertFalse(phase_account_boundary().broker_live_kyc_required_to_start_demo)

    def test_challenge_purchase_still_has_separate_legal_checks(self):
        self.assertTrue(phase_account_boundary().legal_buyer_checks_may_apply_to_challenge_purchase)

    def test_no_real_account_until_two_independent_passes(self):
        self.assertTrue(phase_account_boundary().real_broker_account_only_after_two_verified_passes)

    def test_no_funded_capital_guarantee_at_purchase(self):
        self.assertTrue(phase_account_boundary().no_instant_real_funding_promised)

    def test_no_broker_account_side_effect_from_boundary(self):
        self.assertFalse(phase_account_boundary().real_account_created)

    def test_no_challenge_invoice_side_effect_from_boundary(self):
        self.assertFalse(phase_account_boundary().invoice_created)

    def test_no_payment_side_effect_from_boundary(self):
        self.assertFalse(phase_account_boundary().payment_processed)

    def test_no_fake_kyc_from_boundary(self):
        self.assertFalse(phase_account_boundary().real_broker_kyc_completed)

    def test_single_real_challenge_sku(self):
        self.assertEqual(phase_account_boundary().sku, "MOJ-PROP-01")

    def test_educational_sku_cannot_enter_challenge_boundary(self):
        with self.assertRaises(ValueError):
            phase_account_boundary(sku="MOJPROP-STARTER30")

    def test_wrong_contract_revision_denied(self):
        with self.assertRaises(ValueError):
            phase_account_boundary(terms_version="2026-11-14/v1.1")

    def test_malformed_sku_denied(self):
        with self.assertRaises(ValueError):
            phase_account_boundary(sku=True)

    def test_boolean_terms_denied(self):
        with self.assertRaises(ValueError):
            phase_account_boundary(terms_version=True)

    def test_no_funded_eligibility_from_empty_evidence(self):
        with self.assertRaises(ValueError):
            review_demo_to_real_transition(independently_verified={})

    def test_none_evidence_denied(self):
        with self.assertRaises(TypeError):
            review_demo_to_real_transition(independently_verified=None)

    def test_untrusted_list_evidence_denied(self):
        with self.assertRaises(TypeError):
            review_demo_to_real_transition(independently_verified=[])

    def test_all_missing_one_by_one_block_real_account(self):
        for field in REQUIRED_REAL_ACCOUNT_PROOFS:
            with self.subTest(field=field):
                evidence=self.all_evidence()
                evidence[field]=False
                review=review_demo_to_real_transition(independently_verified=evidence)
                self.assertFalse(review.eligible_for_separate_real_account_review)
                self.assertIn(field, review.missing)
                self.assertFalse(review.verified_real_account_created)

    def test_true_like_integer_is_not_evidence(self):
        evidence=self.all_evidence()
        evidence["broker_kyc_fully_verified"]=1
        review=review_demo_to_real_transition(independently_verified=evidence)
        self.assertFalse(review.eligible_for_separate_real_account_review)

    def test_true_like_string_is_not_evidence(self):
        evidence=self.all_evidence()
        evidence["stage_two_independently_passed"]="true"
        review=review_demo_to_real_transition(independently_verified=evidence)
        self.assertFalse(review.eligible_for_separate_real_account_review)

    def test_extra_approval_field_denied(self):
        evidence=self.all_evidence()
        evidence["skip_broker_kyc"]=True
        with self.assertRaises(ValueError):
            review_demo_to_real_transition(independently_verified=evidence)

    def test_partial_demo_one_pass_is_not_real(self):
        evidence=self.all_evidence()
        evidence["stage_two_independently_passed"]=False
        self.assertFalse(review_demo_to_real_transition(
            independently_verified=evidence).eligible_for_separate_real_account_review)

    def test_both_passed_but_broker_kyc_missing_still_blocked(self):
        evidence=self.all_evidence()
        evidence["broker_kyc_fully_verified"]=False
        self.assertFalse(review_demo_to_real_transition(
            independently_verified=evidence).eligible_for_separate_real_account_review)

    def test_both_passed_but_genuine_funding_missing_still_blocked(self):
        evidence=self.all_evidence()
        evidence["real_100_usd_unencumbered_capital_verified"]=False
        self.assertFalse(review_demo_to_real_transition(
            independently_verified=evidence).eligible_for_separate_real_account_review)

    def test_both_passed_but_contract_missing_still_blocked(self):
        evidence=self.all_evidence()
        evidence["signed_real_funded_account_agreement"]=False
        self.assertFalse(review_demo_to_real_transition(
            independently_verified=evidence).eligible_for_separate_real_account_review)

    def test_all_evidence_only_allows_separate_review(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertTrue(review.eligible_for_separate_real_account_review)
        self.assertEqual(review.status, "READY_FOR_SEPARATE_BROKER_APPROVAL_REVIEW_ONLY")

    def test_even_all_true_never_creates_real_account(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertFalse(review.broker_account_opened_by_this_module)
        self.assertFalse(review.verified_real_account_created)

    def test_even_all_true_never_transfers_real_money(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertFalse(review.real_capital_transferred_by_this_module)

    def test_even_all_true_never_authorizes_real_order(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertFalse(review.live_order_authorized)

    def test_even_all_true_never_issues_challenge_invoice(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertFalse(review.challenge_invoice_created)

    def test_even_all_true_never_generates_marketing_consent(self):
        review=review_demo_to_real_transition(independently_verified=self.all_evidence())
        self.assertFalse(review.marketing_permission_created)

    def test_stage_boundary_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            phase_account_boundary().phase_one_simulated=False

    def test_real_review_result_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            review_demo_to_real_transition(
                independently_verified=self.all_evidence()).live_order_authorized=True

