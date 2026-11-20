"""Offline future-social-post review: no OAuth, browser, TRX or broker writes."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from prop_firm.xauusd_v13_draft_terms import draft_gold_terms_v13
from prop_firm.plan1_buyer_no_social_amendment import buyer_no_social_post_amendment
from prop_firm.xauusd_v13_social_evidence import (
    V13SocialEvidence, review_v13_social_proposal,
)

START = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
MATURE = START + timedelta(days=28)
BASE = V13SocialEvidence(
    platform="instagram",
    post_url="https://www.instagram.com/p/IndependentPost123",
    posted_at=START,
    reviewed_at=MATURE,
    buyer_separately_consented=True,
    operator_claims_independent_review=True,
    original_post_claimed=True,
    continuous_visibility_claimed=True,
    promotion_disclosed_claimed=True,
    no_misleading_profit_claims_claimed=True,
    no_broker_credentials_exposed_claimed=True,
)


def review(evidence=BASE, *, evaluation_started_at=START, as_of=MATURE):
    return review_v13_social_proposal(
        evidence, evaluation_started_at=evaluation_started_at, as_of=as_of,
    )


class V13SocialProposalTests(unittest.TestCase):
    def test_instagram_single_post_is_enough_for_syntactic_preview(self):
        r = review()
        self.assertTrue(r.proposal_evidence_consistent)
        self.assertEqual(r.blockers, ())

    def test_facebook_single_post_is_enough_for_syntactic_preview(self):
        row = replace(BASE, platform="facebook",
                      post_url="https://www.facebook.com/posts/Post123")
        self.assertTrue(review(row).proposal_evidence_consistent)

    def test_exact_28_day_visibility_threshold(self):
        self.assertEqual(review().earliest_eligible_review_at, MATURE)

    def test_27_day_review_denied(self):
        row = replace(BASE, reviewed_at=MATURE-timedelta(days=1))
        r = review(row, as_of=MATURE-timedelta(days=1))
        self.assertIn("post_not_reviewed_after_28_days", r.blockers)

    def test_post_before_challenge_window_denied(self):
        row = replace(BASE, posted_at=START-timedelta(days=1))
        self.assertIn("post_outside_challenge_window", review(row).blockers)

    def test_post_after_challenge_window_denied(self):
        row = replace(BASE, posted_at=START+timedelta(days=29),
                      reviewed_at=START+timedelta(days=57))
        r = review(row, as_of=START+timedelta(days=57))
        self.assertIn("post_outside_challenge_window", r.blockers)

    def test_review_before_post_denied(self):
        row = replace(BASE, reviewed_at=START-timedelta(minutes=1))
        self.assertIn("post_not_reviewed_after_28_days", review(row).blockers)

    def test_review_in_future_denied(self):
        row = replace(BASE, reviewed_at=MATURE+timedelta(hours=1))
        self.assertIn("review_timestamp_is_in_future", review(row).blockers)

    def test_naive_post_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            review(replace(BASE, posted_at=START.replace(tzinfo=None)))

    def test_naive_review_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            review(replace(BASE, reviewed_at=MATURE.replace(tzinfo=None)))

    def test_naive_evaluation_start_rejected(self):
        with self.assertRaises(ValueError):
            review(evaluation_started_at=START.replace(tzinfo=None))

    def test_naive_assessment_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            review(as_of=MATURE.replace(tzinfo=None))

    def test_wrong_platform_rejected(self):
        r = review(replace(BASE, platform="tiktok"))
        self.assertIn("unsupported_platform", r.blockers)

    def test_unencrypted_http_rejected(self):
        r = review(replace(BASE, post_url="http://www.instagram.com/p/Post123"))
        self.assertIn("invalid_or_prohibited_post_url", r.blockers)

    def test_lookalike_domain_rejected(self):
        r = review(replace(BASE, post_url="https://instagram.com.evil.example/p/Id"))
        self.assertIn("invalid_or_prohibited_post_url", r.blockers)

    def test_owner_personal_profile_excluded(self):
        r = review(replace(BASE, post_url="https://www.instagram.com/dr.mojtaba.rozegar/p/Id"))
        self.assertIn("invalid_or_prohibited_post_url", r.blockers)

    def test_tracking_querystring_url_rejected(self):
        r = review(replace(BASE, post_url="https://www.instagram.com/p/Id?token=abc"))
        self.assertIn("invalid_or_prohibited_post_url", r.blockers)

    def test_buyer_consent_must_be_explicit_true(self):
        r = review(replace(BASE, buyer_separately_consented=False))
        self.assertIn("buyer_post_consent_unverified", r.blockers)

    def test_independent_reviewer_claim_must_be_true(self):
        r = review(replace(BASE, operator_claims_independent_review=False))
        self.assertIn("independent_operator_review_unverified", r.blockers)

    def test_original_content_claim_must_be_true(self):
        r = review(replace(BASE, original_post_claimed=False))
        self.assertIn("post_originality_unverified", r.blockers)

    def test_continuous_public_visibility_claim_required(self):
        r = review(replace(BASE, continuous_visibility_claimed=False))
        self.assertIn("28_day_visibility_unverified", r.blockers)

    def test_promotional_disclosure_claim_required(self):
        r = review(replace(BASE, promotion_disclosed_claimed=False))
        self.assertIn("commercial_disclosure_unverified", r.blockers)

    def test_misleading_profit_claim_must_be_excluded(self):
        r = review(replace(BASE, no_misleading_profit_claims_claimed=False))
        self.assertIn("profit_claim_safety_unverified", r.blockers)

    def test_broker_credentials_must_not_be_exposed(self):
        r = review(replace(BASE, no_broker_credentials_exposed_claimed=False))
        self.assertIn("account_privacy_unverified", r.blockers)

    def test_string_true_is_not_a_boolean_attestation(self):
        r = review(replace(BASE, buyer_separately_consented="true"))
        self.assertIn("buyer_post_consent_unverified", r.blockers)

    def test_valid_review_still_never_authorizes_sale_or_trading(self):
        r = review()
        self.assertTrue(r.proposal_evidence_consistent)
        self.assertFalse(r.external_platform_independently_attested)
        self.assertFalse(r.buyer_signed_terms_independently_proven)
        self.assertFalse(r.social_advertising_legally_approved)
        self.assertFalse(r.payable_checkout_authorized)
        self.assertFalse(r.customer_enrollment_authorized)
        self.assertFalse(r.live_broker_order_authorized)
        self.assertFalse(r.outbound_social_publication_authorized)

    def test_wrong_evidence_object_type_rejected(self):
        with self.assertRaises(TypeError):
            review({"platform": "instagram", "posted_at": START})

    def test_new_draft_policy_drift_rejected(self):
        draft = draft_gold_terms_v13()
        with patch("prop_firm.xauusd_v13_social_evidence.draft_gold_terms_v13",
                   return_value=replace(draft, minimum_posts_on_either_platform=2)):
            with self.assertRaises(RuntimeError):
                review()

    def test_assessment_cannot_precede_challenge(self):
        with self.assertRaises(ValueError):
            review(as_of=START-timedelta(seconds=1))

    def test_historical_no_post_waiver_is_unchanged(self):
        old = buyer_no_social_post_amendment()
        new = draft_gold_terms_v13()
        self.assertEqual(old.instagram_posts_required, 0)
        self.assertEqual(old.facebook_posts_required, 0)
        self.assertEqual(new.minimum_posts_on_either_platform, 1)
        self.assertFalse(new.social_customer_terms_signed)


if __name__ == "__main__":
    unittest.main()
