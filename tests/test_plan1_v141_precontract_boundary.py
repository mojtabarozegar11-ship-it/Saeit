"""Source-only contract-version boundary tests, absolutely no money/trades."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from prop_firm.plan1_v14_private_interest_review import (
    ACKNOWLEDGMENTS, review_nonpayable_v14_interest,
)
from prop_firm.plan1_v14_social_or_50_terms import review_prospective_terms
from prop_firm.plan1_v141_precontract_boundary import (
    PrecontractBoundaryClosed, BLOCKERS, STATUS,
    prepare_v141_nonpayable_precontract,
)

NOW=datetime(2026,11,17,13,tzinfo=timezone.utc)


def interest():
    terms=review_prospective_terms()
    form=dict.fromkeys(ACKNOWLEDGMENTS,True)
    form.update(request_ref="REQUEST-ABCDEFGHIJKLMNOP",
                sku=terms.sku,terms_version=terms.version,
                terms_digest_sha256=terms.contract_candidate_sha256,
                self_declared_country="CA",age_at_least_18_self_attested=True,
                request_information_only=True,marketing_consent=False)
    return review_nonpayable_v14_interest(form=form,server_received_at=NOW)


def bind(x=None,**kwargs):
    x=interest() if x is None else x
    return prepare_v141_nonpayable_precontract(
        inquiry=x,expected_request_ref=kwargs.pop("request_ref",x.request_ref),
        expected_comprehension_sha256=kwargs.pop(
            "digest",x.redacted_comprehension_sha256),
        server_now=kwargs.pop("now",NOW),**kwargs,
    )


class NonpayableV141BoundaryTests(unittest.TestCase):
    def test_valid_inquiry_transfers_only_to_private_review(self):
        self.assertEqual(bind().state,STATUS)

    def test_seven_blockers_survive_good_interest(self):
        self.assertEqual(bind().blocker_codes,BLOCKERS)
        self.assertEqual(len(bind().blocker_codes),7)

    def test_pure_review_does_not_issue_payable_invoice(self):
        self.assertFalse(bind().paid_invoice_authorized)

    def test_pure_review_does_not_authorize_tron_checkout(self):
        self.assertFalse(bind().checkout_authorized)

    def test_pure_review_does_not_create_challenge_enrollment(self):
        self.assertFalse(bind().challenge_enrollment_authorized)

    def test_pure_review_does_not_authorize_real_orders(self):
        self.assertFalse(bind().real_orders_authorized)

    def test_pure_review_does_not_approve_payout(self):
        self.assertFalse(bind().payouts_authorized)

    def test_missing_demo_does_not_block_info_request(self):
        self.assertFalse(bind().simulated_phase_completed)
        self.assertEqual(bind().state,STATUS)

    def test_missing_social_post_does_not_block_info_request(self):
        self.assertFalse(bind().social_post_verified)
        self.assertEqual(bind().state,STATUS)

    def test_terms_digest_bound_to_source(self):
        self.assertEqual(bind().contract_sha256,review_prospective_terms().contract_candidate_sha256)

    def test_version_is_not_legacy_v12(self):
        self.assertNotEqual(bind().contract_version,"2026-11-15/v1.2")

    def test_same_exact_request_ref(self):
        self.assertEqual(bind().request_ref,interest().request_ref)

    def test_receipt_timestamp_is_utc(self):
        self.assertEqual(bind().informational_request_received_at_utc,NOW.isoformat())

    def test_wrong_request_ref_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):bind(request_ref="REQUEST-ZZZZZZZZZZZZZZZZ")

    def test_wrong_handoff_intent_digest_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):bind(digest="0"*64)

    def test_invalid_digest_format_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):bind(digest="INVALID")

    def test_wrong_sku_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),sku="MOJPROP-STARTER30"))

    def test_previous_contract_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),terms_version="2026-11-15/v1.2"))

    def test_stale_contract_digest_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),accepted_terms_sha256="0"*64))

    def test_forged_state_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),state="paid_enrollment"))

    def test_claimed_broker_approval_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),broker_permission_verified=True))

    def test_claimed_signed_contract_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),contract_signed=True))

    def test_claimed_payment_release_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),paid_invoice_authorized=True))

    def test_claimed_marketing_opt_in_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),automated_marketing_authorized=True))

    def test_claimed_legal_approval_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),finance_and_advertising_law_cleared=True))

    def test_wrong_date_in_future_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(now=NOW-timedelta(minutes=1))

    def test_naive_server_clock_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(now=NOW.replace(tzinfo=None))

    def test_naive_receipt_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),received_at_utc="2026-11-17T13:00:00"))

    def test_malformed_received_at_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),received_at_utc="fake"))

    def test_bad_declared_country_rejected(self):
        with self.assertRaises(PrecontractBoundaryClosed):
            bind(replace(interest(),declared_country="CA-BC"))

    def test_buyer_identity_is_not_independently_verified(self):
        self.assertFalse(bind().identity_independently_verified)

    def test_signed_customer_contract_is_not_verified(self):
        self.assertFalse(bind().buyer_signed_terms_verified)

    def test_broker_permission_is_not_proven(self):
        self.assertFalse(bind().broker_permission_proven)


if __name__ == "__main__":
    unittest.main()
