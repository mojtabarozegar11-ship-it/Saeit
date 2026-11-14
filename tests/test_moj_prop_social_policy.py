"""Current MOJ PROP policy: ONE retained post on EITHER approved network."""
import unittest
from datetime import datetime, timedelta, timezone

from prop_firm.social_policy import (
    DURATION_DAYS, POST_START_GRACE_HOURS, NEW_CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION, valid_platform_post_url, check_social_posting,
)

START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
MATURE = START + timedelta(days=29)


class OnePostFourWeekPolicyTests(unittest.TestCase):
    def proof(self, platform="instagram", **changes):
        row = {
            "platform": platform,
            "post_url": ("https://www.instagram.com/p/abc123"
                         if platform == "instagram" else
                         "https://www.facebook.com/trader/posts/12345"),
            "posted_at": START + timedelta(hours=1),
            "reviewed_at": START + timedelta(days=28, hours=2),
            "review_status": "verified",
            "reviewed_by_operator": True,
            "author_verified": True,
            "public_visible": True,
            "disclosure_verified": True,
            "content_compliant": True,
            "date_verified": True,
            "continued_visibility_verified": True,
        }
        row.update(changes)
        return row

    def decision(self, proofs=(), when=MATURE):
        return check_social_posting(
            purchase_confirmed_at=START, as_of=when,
            verified_posts=list(proofs),
        )

    def test_policy_is_exactly_28_days(self):
        self.assertEqual(DURATION_DAYS, 28)
        self.assertEqual(POST_START_GRACE_HOURS, 24)

    def test_legacy_and_future_contract_are_distinct(self):
        self.assertNotEqual(LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION)

    def test_one_instagram_post_satisfies_full_cohort(self):
        result = self.decision([self.proof()])
        self.assertTrue(result.satisfied)
        self.assertEqual(result.required_total_posts, 1)
        self.assertEqual(result.reviewed_total_posts, 1)
        self.assertEqual(result.reviewed_instagram, 1)
        self.assertEqual(result.reviewed_facebook, 0)

    def test_one_facebook_post_alone_satisfies_full_cohort(self):
        result = self.decision([self.proof("facebook")])
        self.assertTrue(result.satisfied)
        self.assertEqual(result.reviewed_facebook, 1)
        self.assertEqual(result.reviewed_instagram, 0)

    def test_neither_network_individually_required(self):
        result = self.decision([self.proof("facebook")])
        self.assertEqual(result.required_instagram, 0)
        self.assertEqual(result.required_facebook, 0)

    def test_no_post_has_single_unmet_requirement(self):
        result = self.decision()
        self.assertFalse(result.satisfied)
        self.assertEqual(result.missing_platforms, ("one_post_on_either_platform",))
        self.assertEqual(result.reviewed_total_posts, 0)

    def test_two_posts_do_not_create_two_required_posts(self):
        result = self.decision([self.proof(), self.proof("facebook")])
        self.assertTrue(result.satisfied)
        self.assertEqual(result.required_total_posts, 1)
        self.assertEqual(result.reviewed_total_posts, 1)

    def test_duplicate_post_does_not_count_twice(self):
        row = self.proof()
        result = self.decision([row, row, row])
        self.assertEqual(result.reviewed_total_posts, 1)

    def test_trading_window_not_complete_before_28_days(self):
        result = self.decision(
            [self.proof()], when=START + timedelta(days=27),
        )
        self.assertFalse(result.satisfied)
        self.assertFalse(result.challenge_window_complete)

    def test_visible_28_days_must_be_independently_reviewed(self):
        row = self.proof(reviewed_at=START + timedelta(days=27))
        self.assertFalse(self.decision([row]).satisfied)

    def test_post_must_last_28_days_from_publication(self):
        row = self.proof(
            posted_at=START + timedelta(hours=20),
            reviewed_at=START + timedelta(days=28, hours=19),
        )
        self.assertFalse(self.decision([row]).satisfied)

    def test_post_may_be_created_within_24_hours(self):
        row = self.proof(
            posted_at=START + timedelta(hours=24),
            reviewed_at=START + timedelta(days=29),
        )
        self.assertTrue(self.decision([row],when=START + timedelta(days=30)).satisfied)

    def test_post_after_24_hours_is_not_valid(self):
        row = self.proof(posted_at=START + timedelta(hours=25))
        self.assertFalse(self.decision([row]).satisfied)

    def test_post_before_purchase_does_not_qualify(self):
        row = self.proof(posted_at=START - timedelta(hours=1))
        self.assertFalse(self.decision([row]).satisfied)

    def test_independent_review_from_future_is_rejected(self):
        row = self.proof(reviewed_at=MATURE + timedelta(hours=1))
        self.assertFalse(self.decision([row]).satisfied)

    def test_pending_and_rejected_posts_do_not_qualify(self):
        for status in ("pending", "rejected", "paid", True):
            with self.subTest(status=status):
                self.assertFalse(
                    self.decision([self.proof(review_status=status)]).satisfied
                )

    def test_all_six_manual_review_facts_are_required(self):
        for field in (
            "reviewed_by_operator", "author_verified", "public_visible",
            "disclosure_verified", "content_compliant", "date_verified",
            "continued_visibility_verified",
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    self.decision([self.proof(**{field: False})]).satisfied
                )

    def test_truthy_string_is_not_verified(self):
        self.assertFalse(self.decision(
            [self.proof(continued_visibility_verified="yes")]
        ).satisfied)

    def test_missing_fields_never_reach_approval(self):
        self.assertFalse(self.decision(
            [{"platform": "instagram", "post_url": "https://www.instagram.com/p/abc"}]
        ).satisfied)

    def test_unsupported_network_cannot_substitute(self):
        self.assertFalse(self.decision([self.proof("tiktok")]).satisfied)

    def test_banned_owner_profile_is_not_valid_url(self):
        self.assertFalse(valid_platform_post_url(
            "https://instagram.com/p/dr.mojtaba.rozegar", "instagram"
        ))

    def test_external_and_misleading_hosts_blocked(self):
        for url in (
            "https://facebook.com.evil.example/trader/posts/123",
            "http://www.instagram.com/p/abc",
            "https://user@www.instagram.com/p/abc",
            "https://www.instagram.com/p/abc?tracking=1",
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, "instagram"))

    def test_profile_page_cannot_replace_post(self):
        self.assertFalse(valid_platform_post_url(
            "https://www.instagram.com/anytrader", "instagram"
        ))

    def test_facebook_post_permalink_is_accepted(self):
        self.assertTrue(valid_platform_post_url(
            "https://www.facebook.com/trader/posts/12345", "facebook"
        ))

    def test_naive_purchase_time_rejected(self):
        with self.assertRaises(ValueError):
            check_social_posting(
                purchase_confirmed_at=START.replace(tzinfo=None),
                as_of=MATURE, verified_posts=[],
            )

    def test_assessment_before_purchase_rejected(self):
        with self.assertRaises(ValueError):
            self.decision(when=START - timedelta(minutes=1))

    def test_untrusted_evidence_collection_rejected(self):
        with self.assertRaises(ValueError):
            check_social_posting(
                purchase_confirmed_at=START, as_of=MATURE,
                verified_posts={"platform": "instagram"},
            )

    def test_auto_posting_is_never_allowed(self):
        self.assertFalse(self.decision([self.proof()]).automated_publishing_allowed)

    def test_manual_review_is_always_required(self):
        self.assertTrue(self.decision([self.proof()]).manual_review_required)


if __name__ == "__main__":
    unittest.main()
