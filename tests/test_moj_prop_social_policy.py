"""No platform access, fabricated testimonials or automatic social posting."""
import unittest
from datetime import date, datetime, timedelta, timezone
from prop_firm.social_policy import (
    PLATFORMS, NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION,
    valid_platform_post_url, check_social_posting, utc_day,
)


class SocialPostingPolicyTests(unittest.TestCase):
    DAYS = (date(2026,11,16), date(2026,11,17), date(2026,11,18),
            date(2026,11,19), date(2026,11,20), date(2026,11,21))

    @staticmethod
    def example(day, platform, **changes):
        original = {
            "trading_day": day,
            "platform": platform,
            "post_url": (
                "https://www.instagram.com/p/example123/"
                if platform == "instagram"
                else "https://www.facebook.com/trader/posts/12345"
            ),
            "review_status": "verified",
            "reviewed_by_operator": True,
            "author_verified": True,
            "public_visible": True,
            "disclosure_verified": True,
            "content_compliant": True,
            "date_verified": True,
        }
        original.update(changes)
        return original

    def test_two_distinct_platforms_required(self):
        self.assertEqual(PLATFORMS, ("instagram", "facebook"))

    def test_six_valid_days_require_six_per_platform(self):
        rows = [self.example(day, p) for day in self.DAYS for p in PLATFORMS]
        state = check_social_posting(
            verified_trading_dates=self.DAYS, verified_posts=rows,
        )
        self.assertTrue(state.satisfied)
        self.assertEqual(state.trading_days, 6)
        self.assertEqual(state.required_instagram, 6)
        self.assertEqual(state.required_facebook, 6)
        self.assertEqual(state.reviewed_instagram, 6)
        self.assertEqual(state.reviewed_facebook, 6)
        self.assertFalse(state.automated_publishing_allowed)

    def test_missing_one_facebook_post_blocks_phase(self):
        rows = [self.example(day,p) for day in self.DAYS for p in PLATFORMS]
        rows.pop()
        state = check_social_posting(verified_trading_dates=self.DAYS, verified_posts=rows)
        self.assertFalse(state.satisfied)
        self.assertEqual(len(state.missing_days), 1)
        self.assertTrue(state.missing_days[0].endswith(":facebook"))

    def test_extra_trade_day_requires_extra_posts(self):
        days = self.DAYS + (date(2026,11,22),)
        rows = [self.example(day,p) for day in self.DAYS for p in PLATFORMS]
        state = check_social_posting(verified_trading_dates=days, verified_posts=rows)
        self.assertFalse(state.satisfied)
        self.assertEqual(len(state.missing_days), 2)
        self.assertEqual(state.required_instagram, 7)

    def test_no_trade_dates_never_produce_pass(self):
        state = check_social_posting(verified_trading_dates=(), verified_posts=())
        self.assertFalse(state.satisfied)

    def test_posts_on_nontrading_days_do_not_substitute(self):
        rows = [self.example(date(2026,11,22),p) for p in PLATFORMS]
        state = check_social_posting(
            verified_trading_dates=(self.DAYS[0],), verified_posts=rows,
        )
        self.assertFalse(state.satisfied)

    def test_pending_or_rejected_posts_never_count(self):
        for status in ("pending", "rejected", "paid", "approved", 1):
            with self.subTest(status=status):
                rows = [self.example(self.DAYS[0],"instagram",review_status=status)]
                self.assertEqual(check_social_posting(
                    verified_trading_dates=(self.DAYS[0],), verified_posts=rows
                ).reviewed_instagram,0)

    def test_each_operator_review_fact_required(self):
        for key in ("reviewed_by_operator","author_verified","public_visible",
                    "disclosure_verified","content_compliant","date_verified"):
            with self.subTest(field=key):
                rows = [self.example(self.DAYS[0],p) for p in PLATFORMS]
                rows[0][key] = False
                self.assertFalse(check_social_posting(
                    verified_trading_dates=(self.DAYS[0],), verified_posts=rows
                ).satisfied)

    def test_truthy_reviewer_flags_are_not_verified(self):
        row = self.example(self.DAYS[0],"instagram",reviewed_by_operator="yes")
        result = check_social_posting(
            verified_trading_dates=(self.DAYS[0],),verified_posts=[row]
        )
        self.assertEqual(result.reviewed_instagram, 0)

    def test_instagram_post_or_reel_but_not_profile(self):
        self.assertTrue(valid_platform_post_url("https://instagram.com/p/abc123/", "instagram"))
        self.assertTrue(valid_platform_post_url("https://www.instagram.com/reel/abc123", "instagram"))
        self.assertFalse(valid_platform_post_url("https://www.instagram.com/trader", "instagram"))

    def test_facebook_post_url_not_external_shorteners(self):
        self.assertTrue(valid_platform_post_url(
            "https://www.facebook.com/trader/posts/12345", "facebook"
        ))
        for url in ("https://facebook.com.evil.net/trader/posts/123",
                    "http://facebook.com/trader/posts/123",
                    "https://evil.com/trader/posts/123"):
            self.assertFalse(valid_platform_post_url(url,"facebook"))

    def test_owner_banned_profile_not_a_valid_post(self):
        self.assertFalse(valid_platform_post_url(
            "https://instagram.com/p/dr.mojtaba.rozegar", "instagram"
        ))

    def test_url_query_tracking_and_fragments_are_rejected(self):
        for url in (
            "https://instagram.com/p/abcdef/?email=trader@example.com",
            "https://instagram.com/p/abcdef/#fragment",
            "https://attacker@instagram.com/p/abc123",
        ):
            self.assertFalse(valid_platform_post_url(url,"instagram"))

    def test_consent_and_legacy_contract_version_distinct(self):
        self.assertNotEqual(NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION)

    def test_utc_date_normalization_requires_aware_datetime(self):
        self.assertEqual(utc_day(datetime(2026,11,16,0,30,tzinfo=timezone.utc)),
                         self.DAYS[0])
        with self.assertRaises(ValueError):
            utc_day(datetime(2026,11,16,12,0))

    def test_untrusted_post_record_is_ignored(self):
        state = check_social_posting(
            verified_trading_dates=(self.DAYS[0],),
            verified_posts=[{"platform":"instagram"}],
        )
        self.assertFalse(state.satisfied)

    def test_duplicated_posts_do_not_count_twice(self):
        rows = [self.example(self.DAYS[0], "instagram")] * 5
        result = check_social_posting(
            verified_trading_dates=(self.DAYS[0],), verified_posts=rows
        )
        self.assertEqual(result.reviewed_instagram, 1)
        self.assertFalse(result.satisfied)

    def test_bad_trading_days_rejected(self):
        for dates in ("2026-11-16", (datetime.now(timezone.utc),), (1,)):
            with self.subTest(dates=str(dates)), self.assertRaises(ValueError):
                check_social_posting(verified_trading_dates=dates,verified_posts=())


if __name__ == "__main__":
    unittest.main()
