"""One Instagram and one Facebook post kept public for four weeks, not daily."""
import unittest
from datetime import datetime, timedelta, timezone

from prop_firm.social_policy import (
    DURATION_DAYS, PLATFORMS, POST_START_GRACE_HOURS,
    NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION,
    check_social_posting, valid_platform_post_url,
)

PURCHASE = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
MATURITY = PURCHASE + timedelta(days=28)


class SinglePostFourWeekTests(unittest.TestCase):
    def evidence(self, platform, **extra):
        data = {
            "platform": platform,
            "post_url": (
                "https://www.instagram.com/p/abc123"
                if platform == "instagram" else
                "https://www.facebook.com/trader/posts/123456"
            ),
            "posted_at": PURCHASE,
            "reviewed_at": MATURITY,
            "review_status": "verified",
            "reviewed_by_operator": True,
            "author_verified": True,
            "public_visible": True,
            "disclosure_verified": True,
            "content_compliant": True,
            "date_verified": True,
            "continued_visibility_verified": True,
        }
        data.update(extra)
        return data

    def check(self, *, as_of=MATURITY, posts=None):
        return check_social_posting(
            purchase_confirmed_at=PURCHASE, as_of=as_of,
            verified_posts=([self.evidence(p) for p in PLATFORMS]
                            if posts is None else posts),
        )

    def test_only_two_total_posts_per_purchase(self):
        result = self.check()
        self.assertTrue(result.satisfied)
        self.assertEqual((result.required_instagram, result.required_facebook), (1,1))
        self.assertEqual((result.reviewed_instagram, result.reviewed_facebook), (1,1))

    def test_challenge_exactly_twenty_eight_days(self):
        self.assertEqual(DURATION_DAYS, 28)
        self.assertEqual(self.check().challenge_ends_at, MATURITY)
        self.assertTrue(self.check().challenge_window_complete)
        self.assertFalse(self.check(as_of=MATURITY-timedelta(seconds=1)).satisfied)

    def test_one_post_per_network_enough_with_any_number_of_trade_days(self):
        # No trading-day field exists in this requirement.
        self.assertTrue(self.check().satisfied)

    def test_one_instagram_alone_cannot_pass(self):
        result = self.check(posts=[self.evidence("instagram")])
        self.assertFalse(result.satisfied)
        self.assertEqual(result.missing_platforms, ("facebook",))

    def test_one_facebook_alone_cannot_pass(self):
        result = self.check(posts=[self.evidence("facebook")])
        self.assertEqual(result.missing_platforms, ("instagram",))

    def test_one_hour_late_post_needs_full_lifetime_from_actual_post(self):
        late = PURCHASE + timedelta(hours=1)
        posts = [
            self.evidence("instagram", posted_at=late, reviewed_at=late+timedelta(days=28)),
            self.evidence("facebook"),
        ]
        self.assertFalse(self.check(as_of=MATURITY, posts=posts).satisfied)
        self.assertTrue(self.check(as_of=late+timedelta(days=28), posts=posts).satisfied)

    def test_at_twenty_seven_days_posts_are_not_mature(self):
        posts = [self.evidence(p, reviewed_at=MATURITY-timedelta(days=1)) for p in PLATFORMS]
        self.assertFalse(self.check(posts=posts).satisfied)

    def test_post_too_late_after_purchase_rejected(self):
        later = PURCHASE + timedelta(hours=25)
        posts = [
            self.evidence("instagram",posted_at=later, reviewed_at=later+timedelta(days=28)),
            self.evidence("facebook"),
        ]
        self.assertFalse(self.check(as_of=later+timedelta(days=28), posts=posts).satisfied)

    def test_missing_public_visibility_blocks_pass(self):
        rows = [self.evidence("instagram",continued_visibility_verified=False),
                self.evidence("facebook")]
        self.assertFalse(self.check(posts=rows).satisfied)

    def test_no_fake_reviews_or_ad_disclosure_omission(self):
        for flag in (
            "reviewed_by_operator","author_verified","public_visible",
            "disclosure_verified","content_compliant","date_verified",
            "continued_visibility_verified",
        ):
            with self.subTest(flag=flag):
                rows = [self.evidence("instagram",**{flag:False}),self.evidence("facebook")]
                self.assertFalse(self.check(posts=rows).satisfied)

    def test_approval_like_strings_do_not_count(self):
        rows = [self.evidence("instagram",reviewed_by_operator="yes"),
                self.evidence("facebook")]
        self.assertFalse(self.check(posts=rows).satisfied)

    def test_review_cannot_be_future_dated_for_as_of(self):
        rows = [self.evidence("instagram",reviewed_at=MATURITY+timedelta(days=1)),
                self.evidence("facebook")]
        self.assertFalse(self.check(posts=rows).satisfied)

    def test_no_challenge_without_both_posts(self):
        self.assertFalse(self.check(posts=[]).satisfied)

    def test_malformed_record_does_not_forge_approval(self):
        self.assertFalse(self.check(posts=[{"platform":"instagram"}]).satisfied)

    def test_valid_https_domains_and_no_owner_profile(self):
        self.assertTrue(valid_platform_post_url("https://instagram.com/p/abc123","instagram"))
        self.assertTrue(valid_platform_post_url(
            "https://www.facebook.com/trader/posts/12345","facebook"))
        for url in (
            "https://instagram.com.evil.org/p/x",
            "http://instagram.com/p/x",
            "https://www.instagram.com/dr.mojtaba.rozegar",
        ):
            self.assertFalse(valid_platform_post_url(url,"instagram"))

    def test_no_automatic_social_publishing(self):
        self.assertFalse(self.check().automated_publishing_allowed)

    def test_legacy_version_is_distinct(self):
        self.assertNotEqual(NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION)

    def test_no_unaudited_or_naive_purchase_timestamp(self):
        with self.assertRaises(ValueError):
            check_social_posting(
                purchase_confirmed_at=datetime(2026,10,1,12), as_of=MATURITY,
                verified_posts=[],
            )

    def test_24_hour_initial_publication_window(self):
        self.assertEqual(POST_START_GRACE_HOURS,24)


if __name__ == "__main__":
    unittest.main()
