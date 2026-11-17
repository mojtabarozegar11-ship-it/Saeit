"""Offline-only v1.4 terms, fifty-trade and 28-day Instagram OR Facebook review."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

from prop_firm.plan1_v14_social_or_50_terms import (
    review_prospective_terms, VERSION, SOCIAL_DURATION_HOURS,
)
from prop_firm.plan1_v14_social_or_28d_review import (
    SocialPostClaim, review_social_post_28d,
)
from prop_firm.xauusd_v13_draft_terms import draft_gold_terms_v13

POSTED = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
NOW = POSTED + timedelta(days=28)


def claim(platform="instagram", url="https://www.instagram.com/p/abc123/",
          **changes):
    observations = tuple(POSTED + timedelta(days=i) for i in range(29))
    fields = dict(platform=platform, url=url,
                  published_at=POSTED,
                  public_visibility_snapshots=observations,
                  is_original_claimed=True,
                  participation_disclosure_claimed=True,
                  participant_is_not_owner_claimed=True)
    fields.update(changes)
    return SocialPostClaim(**fields)


def review(c=None, *, now=NOW):
    return review_social_post_28d(claim() if c is None else c, now=now)


class ProspectiveV14ContractTests(unittest.TestCase):
    def test_new_version_unique_from_unsigned_v13(self):
        d=review_prospective_terms()
        self.assertEqual(d.version, VERSION)
        self.assertNotEqual(d.version,d.supersedes_unsigned_draft_version)

    def test_exact_product_and_fifty_closed_total(self):
        d=review_prospective_terms()
        self.assertEqual(d.sku,"MOJ-PROP-01")
        self.assertEqual(d.closed_trades_total,50)
        self.assertIn("NOT 50 per phase",d.en)
        self.assertIn("نه ۵۰ معامله در هر مرحله",d.fa)

    def test_six_days_each_stage(self):
        d=review_prospective_terms()
        self.assertEqual(d.trading_days_each_phase,6)
        self.assertIn("SIX independently",d.en)

    def test_or_is_not_and(self):
        d=review_prospective_terms()
        self.assertEqual(d.social_platform_operator,"OR")
        self.assertEqual(d.social_platforms,("instagram","facebook"))
        self.assertEqual(d.social_posts_required,1)
        self.assertIn("EITHER",d.en)
        self.assertIn("یا فیس‌بوک",d.fa)

    def test_at_least_one_not_exactly_one_post_contract(self):
        x=review_prospective_terms()
        self.assertIn("at least ONE qualifying original post",x.en)
        self.assertIn("حداقل یک پست اصلی واجد شرایط",x.fa)
        self.assertNotIn("exactly ONE",x.en)
        self.assertNotIn("دقیقاً یک پست",x.fa)

    def test_social_and_demo_twenty_eight_day_clocks_are_distinct(self):
        x=review_prospective_terms()
        self.assertIn("SEPARATE clocks",x.en)
        self.assertIn("مستقل هستند",x.fa)
        self.assertIn("final social qualification must wait",x.en)

    def test_exact_28_day_hold(self):
        d=review_prospective_terms()
        self.assertEqual(d.public_post_hours,672)
        self.assertEqual(SOCIAL_DURATION_HOURS,672)

    def test_post_must_disclose_relation(self):
        self.assertTrue(review_prospective_terms().social_post_disclosure_required)

    def test_lawful_promotion_not_presumed(self):
        d=review_prospective_terms()
        self.assertFalse(d.legal_social_advertising_clearance)

    def test_historical_contracts_unchanged(self):
        d=review_prospective_terms()
        self.assertFalse(d.existing_agreements_amended)
        self.assertEqual(d.supersedes_unsigned_draft_version,
                         draft_gold_terms_v13().contract_version)

    def test_no_charge_enrollment_or_trading(self):
        d=review_prospective_terms()
        self.assertFalse(d.checkout_enabled)
        self.assertFalse(d.enrollment_enabled)
        self.assertFalse(d.real_trading_enabled)
        self.assertFalse(d.payout_enabled)
        self.assertFalse(d.customer_terms_signed)

    def test_no_broker_or_cash_claim(self):
        d=review_prospective_terms()
        self.assertFalse(d.broker_permission_verified)
        self.assertFalse(d.cash_reserves_verified)

    def test_digest_stable_and_distinct(self):
        a,b=review_prospective_terms(),review_prospective_terms()
        self.assertEqual(a.contract_candidate_sha256,b.contract_candidate_sha256)
        self.assertRegex(a.contract_candidate_sha256,r"^[0-9a-f]{64}$")
        self.assertNotEqual(a.contract_candidate_sha256,a.source_draft_sha256)

    def test_parent_term_drift_blocks_new_contract(self):
        before=draft_gold_terms_v13()
        with patch("prop_firm.plan1_v14_social_or_50_terms.draft_gold_terms_v13",
                   return_value=replace(before,min_closed_trades_total=49)):
            with self.assertRaises(ValueError): review_prospective_terms()

    def test_parent_checkout_flag_blocks_new_contract(self):
        before=draft_gold_terms_v13()
        with patch("prop_firm.plan1_v14_social_or_50_terms.draft_gold_terms_v13",
                   return_value=replace(before,checkout_enabled=True)):
            with self.assertRaises(ValueError): review_prospective_terms()


class SocialPost28DayTests(unittest.TestCase):
    def test_valid_instagram_timeline_is_only_math(self):
        a=review()
        self.assertTrue(a.timeline_mathematically_consistent)
        self.assertEqual(a.observed_hours,672)
        self.assertFalse(a.social_post_independently_verified)
        self.assertFalse(a.legal_approval_verified)
        self.assertFalse(a.customer_checkout_authorized)

    def test_valid_facebook_or_path(self):
        a=review(claim(platform="facebook",
                       url="https://www.facebook.com/example/posts/abcdef"))
        self.assertTrue(a.timeline_mathematically_consistent)
        self.assertFalse(a.terms_signed)

    def test_27_days_fails(self):
        a=review(now=POSTED+timedelta(days=27))
        self.assertIn("twenty_eight_full_days_not_elapsed",a.reasons)

    def test_28_day_end_observation_missing(self):
        e=claim()
        a=review(replace(e,public_visibility_snapshots=e.public_visibility_snapshots[:-1]))
        self.assertIn("end_of_visibility_not_observed",a.reasons)

    def test_visibility_gap_over_24h(self):
        e=claim()
        t=e.public_visibility_snapshots
        a=review(replace(e,public_visibility_snapshots=t[:5]+t[6:]))
        self.assertIn("daily_visibility_evidence_has_gap_or_replay",a.reasons)

    def test_observation_replay_blocked(self):
        e=claim()
        t=list(e.public_visibility_snapshots)
        t[1]=t[0]
        self.assertIn("daily_visibility_evidence_has_gap_or_replay",
                      review(replace(e,public_visibility_snapshots=tuple(t))).reasons)

    def test_missing_disclosure_fails(self):
        e=claim(participation_disclosure_claimed=False)
        self.assertIn("participant_relationship_not_disclosed",review(e).reasons)

    def test_not_original_fails(self):
        self.assertIn("post_originality_not_claimed",
                      review(claim(is_original_claimed=False)).reasons)

    def test_owner_account_fails(self):
        self.assertIn("owner_account_post_forbidden",
                      review(claim(participant_is_not_owner_claimed=False)).reasons)

    def test_bad_social_platform_fails(self):
        self.assertIn("unsupported_or_unsafe_post_url",
                      review(claim(platform="tiktok")).reasons)

    def test_fake_subdomain_rejected(self):
        self.assertIn("unsupported_or_unsafe_post_url",
                      review(claim(url="https://instagram.com.evil.com/p/abc123/")).reasons)

    def test_query_tracking_or_redirect_rejected(self):
        self.assertIn("unsupported_or_unsafe_post_url",
                      review(claim(url="https://instagram.com/p/abc123/?to=bad")).reasons)

    def test_invalid_website_protocol(self):
        self.assertIn("unsupported_or_unsafe_post_url",
                      review(claim(url="http://instagram.com/p/abc123/")).reasons)

    def test_untrusted_list_type_rejected(self):
        e=claim()
        with self.assertRaises(ValueError):
            review(replace(e,public_visibility_snapshots=list(e.public_visibility_snapshots)))

    def test_future_publication_rejected(self):
        a=review(claim(published_at=NOW+timedelta(hours=1)))
        self.assertIn("publication_in_future",a.reasons)

    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            review(now=NOW.replace(tzinfo=None))

    def test_oversized_snapshot_log_rejected(self):
        e=claim()
        with self.assertRaises(ValueError):
            review(replace(e,public_visibility_snapshots=tuple([POSTED]*257)))

    def test_missing_initial_snapshot(self):
        e=claim()
        t=e.public_visibility_snapshots
        a=review(replace(e,public_visibility_snapshots=t[1:]))
        self.assertIn("initial_visibility_not_observed",a.reasons)

    def test_post_as_financial_recommendation_not_approved(self):
        a=review()
        self.assertFalse(a.customer_enrollment_authorized)
        self.assertFalse(a.broker_live_orders_authorized)
        self.assertFalse(a.payout_authorized)


if __name__=="__main__":
    unittest.main()
