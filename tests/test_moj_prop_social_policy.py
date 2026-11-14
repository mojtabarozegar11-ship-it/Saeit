"""C22 exact v1.2: one original post on each platform, visible for 28 days.

This is *only* offline review of a prospective, legally gated contract.
It never publishes a post or accepts money.
"""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from prop_firm.social_policy import (
    PLATFORMS, DURATION_DAYS, POST_START_GRACE_HOURS,
    BLOCKED_OWNER_PROFILE, BLOCKED_OWNER_FACEBOOK_PAGE_ID,
    NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION,
    check_social_posting, valid_platform_post_url,
)

START = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
NOW = START + timedelta(days=29)


def proof(platform, **changes):
    posted = START + timedelta(hours=2)
    values = {
        "platform": platform,
        "post_url": (
            "https://www.instagram.com/p/example123"
            if platform == "instagram"
            else "https://www.facebook.com/trader/posts/123456789"
        ),
        "posted_at": posted,
        "reviewed_at": posted + timedelta(days=28, hours=1),
        "review_status": "verified",
        "reviewed_by_operator": True,
        "author_verified": True,
        "public_visible": True,
        "disclosure_verified": True,
        "content_compliant": True,
        "date_verified": True,
        "continued_visibility_verified": True,
    }
    values.update(changes)
    return values


def decision(posts, at=NOW):
    return check_social_posting(
        purchase_confirmed_at=START, as_of=at, verified_posts=posts,
    )


class Prospective28DaySocialPolicyTests(unittest.TestCase):
    def test_exact_owner_contract_one_post_each_platform(self):
        self.assertEqual(PLATFORMS, ("instagram", "facebook"))
        self.assertEqual(DURATION_DAYS, 28)
        self.assertEqual(POST_START_GRACE_HOURS, 24)
        self.assertNotEqual(LEGACY_CONTRACT_VERSION, NEW_CONTRACT_VERSION)

    def test_single_post_on_both_platforms_satisfies_only_after_visibility(self):
        result = decision([proof("instagram"), proof("facebook")])
        self.assertTrue(result.satisfied)
        self.assertEqual(result.required_instagram, 1)
        self.assertEqual(result.required_facebook, 1)
        self.assertEqual(result.reviewed_instagram, 1)
        self.assertEqual(result.reviewed_facebook, 1)
        self.assertEqual(result.missing_platforms, ())
        self.assertFalse(result.automated_publishing_allowed)

    def test_challenge_just_before_28_days_cannot_pass(self):
        p = [proof("instagram"), proof("facebook")]
        result = decision(p, START + timedelta(days=27, hours=23))
        self.assertFalse(result.satisfied)
        self.assertFalse(result.challenge_window_complete)

    def test_post_visibility_is_28_days_from_post_not_purchase(self):
        t = START + timedelta(days=28)
        r = decision([proof("instagram"), proof("facebook")], t)
        self.assertFalse(r.satisfied)
        self.assertTrue(r.challenge_window_complete)
        self.assertEqual(r.required_visible_until, START + timedelta(days=28))

    def test_missing_facebook_always_blocks(self):
        r = decision([proof("instagram")])
        self.assertFalse(r.satisfied)
        self.assertEqual(r.missing_platforms, ("facebook",))

    def test_missing_instagram_always_blocks(self):
        r = decision([proof("facebook")])
        self.assertFalse(r.satisfied)
        self.assertEqual(r.missing_platforms, ("instagram",))

    def test_no_posts_no_pass(self):
        r = decision([])
        self.assertFalse(r.satisfied)
        self.assertEqual(r.reviewed_instagram + r.reviewed_facebook, 0)

    def test_pending_or_rejected_never_counts(self):
        for status in ("pending", "rejected", "approved", 1, True):
            with self.subTest(status=str(status)):
                r = decision([proof("instagram", review_status=status), proof("facebook")])
                self.assertFalse(r.satisfied)

    def test_each_review_attestation_must_be_literal_true(self):
        fields = (
            "reviewed_by_operator", "author_verified", "public_visible",
            "disclosure_verified", "content_compliant", "date_verified",
            "continued_visibility_verified",
        )
        for field in fields:
            for value in (False, "yes", 1, None):
                with self.subTest(field=field, value=value):
                    r = decision([proof("instagram", **{field: value}), proof("facebook")])
                    self.assertFalse(r.satisfied)

    def test_review_prior_to_28_day_post_maturity_rejected(self):
        a = proof("instagram", reviewed_at=START + timedelta(days=3))
        self.assertFalse(decision([a, proof("facebook")]).satisfied)

    def test_unaudited_28day_observation_does_not_count(self):
        row = proof("instagram", continued_visibility_verified=False)
        self.assertFalse(decision([row, proof("facebook")]).satisfied)

    def test_future_or_before_purchase_post_does_not_count(self):
        early = proof("instagram", posted_at=START - timedelta(seconds=1))
        late = proof("instagram", posted_at=START + timedelta(hours=25))
        self.assertFalse(decision([early, proof("facebook")]).satisfied)
        self.assertFalse(decision([late, proof("facebook")]).satisfied)

    def test_review_after_as_of_is_not_backdated_to_approval(self):
        row = proof("instagram", reviewed_at=NOW + timedelta(days=1))
        self.assertFalse(decision([row, proof("facebook")]).satisfied)

    def test_multiple_copies_of_one_post_do_not_replace_other_platform(self):
        r = decision([proof("instagram")] * 9)
        self.assertFalse(r.satisfied)
        self.assertEqual(r.reviewed_instagram, 1)
        self.assertEqual(r.reviewed_facebook, 0)

    def test_profile_urls_do_not_count_as_public_post(self):
        self.assertFalse(valid_platform_post_url("https://instagram.com/trader", "instagram"))
        self.assertFalse(valid_platform_post_url("https://facebook.com/trader", "facebook"))

    def test_realistic_post_shapes_are_accepted_without_publication(self):
        self.assertTrue(valid_platform_post_url("https://www.instagram.com/reel/abcDEF123/", "instagram"))
        self.assertTrue(valid_platform_post_url("https://facebook.com/trader/posts/12345", "facebook"))
        self.assertTrue(valid_platform_post_url("https://facebook.com/posts/12345", "facebook"))

    def test_all_owner_personal_aliases_are_forbidden(self):
        bad = (
            ("https://www.instagram.com/p/dr.mojtaba.rozegar", "instagram"),
            ("https://www.facebook.com/dr.mojtaba.rozegar/posts/12345", "facebook"),
            ("https://www.facebook.com/102203064721826/posts/12345", "facebook"),
            ("https://www.facebook.com/7317306/posts/12345", "facebook"),
            ("https://www.instagram.com/p/102203064721826", "instagram"),
        )
        for url, platform in bad:
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, platform))
        self.assertEqual(BLOCKED_OWNER_PROFILE, "dr.mojtaba.rozegar")
        self.assertEqual(BLOCKED_OWNER_FACEBOOK_PAGE_ID, "102203064721826")

    def test_encoded_blocked_urls_and_invisible_chars_are_rejected(self):
        for url in (
            "https://facebook.com/%31%30%32%32%30%33%30%36%34%37%32%31%38%32%36/posts/12345",
            "https://facebook.com/102203064721826%2fposts/12345",
            "https://instagram.com/p/%64r.mojtaba.rozegar",
            "https://instagram.com/p/abc123%2f",
            "https://instagram.com/p/a\u200bbc123",
            "https://facebook.com/trader\\posts\\12345",
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, "facebook")
                                 if "facebook" in url else valid_platform_post_url(url, "instagram"))

    def test_host_and_scheme_impersonation_rejected(self):
        for url in (
            "http://instagram.com/p/abc123",
            "https://instagram.com.evil.org/p/abc123",
            "https://someone@instagram.com/p/abc123",
            "https://facebook.com.evil.org/trader/posts/12345",
            "https://facebook.com:443/trader/posts/12345",
        ):
            platform = "facebook" if "facebook" in url else "instagram"
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, platform))

    def test_query_fragment_and_extra_path_segments_rejected(self):
        for url, platform in (
            ("https://instagram.com/p/abc123/?tracking=yes", "instagram"),
            ("https://instagram.com/p/abc123/#x", "instagram"),
            ("https://instagram.com/p/abc123/extra", "instagram"),
            ("https://facebook.com/trader/posts/12345/extra", "facebook"),
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, platform))

    def test_malformed_record_is_not_approved(self):
        self.assertFalse(decision([{"platform": "instagram"}]).satisfied)
        self.assertFalse(decision([proof("instagram", extra="nonsense"), proof("facebook")]).satisfied)

    def test_unaware_purchase_and_review_times_fail_closed(self):
        with self.assertRaises(ValueError):
            check_social_posting(
                purchase_confirmed_at=START.replace(tzinfo=None),
                as_of=NOW, verified_posts=[],
            )
        self.assertFalse(decision([
            proof("instagram", reviewed_at=NOW.replace(tzinfo=None)),
            proof("facebook"),
        ]).satisfied)

    def test_unaware_now_rejected(self):
        with self.assertRaises(ValueError):
            decision([], NOW.replace(tzinfo=None))

    def test_no_meta_api_or_paid_qualification_in_decision(self):
        r = decision([proof("instagram"), proof("facebook")])
        self.assertTrue(r.manual_review_required)
        self.assertFalse(r.automated_publishing_allowed)
        self.assertFalse(hasattr(r, "checkout_enabled"))
        self.assertFalse(hasattr(r, "funded_trading_enabled"))


if __name__ == "__main__":
    unittest.main()
