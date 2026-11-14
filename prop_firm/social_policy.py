"""Moj Prop 28-day single-post evidence policy, prospective v1.2 only.

Exactly one original Instagram and one original Facebook post for the *entire*
challenge enrollment (two phases combined), not per trade or per phase.
The four-week trading window begins at an independently confirmed paid invoice,
not at a user-supplied browser timestamp. Posts must remain visible for at
least 28 x 24 hours. A completed trading window never substitutes for confirmed
28-day post visibility. All checks are offline; no Meta API writes.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import re

PLATFORMS = ("instagram", "facebook")
LEGACY_CONTRACT_VERSION = "2026-11-14/v1.1"
NEW_CONTRACT_VERSION = "2026-11-15/v1.2"
DURATION_DAYS = 28
POST_START_GRACE_HOURS = 24
BLOCKED_OWNER_PROFILE = "dr.mojtaba.rozegar"
BLOCKED_OWNER_FACEBOOK_PAGE_ID = "102203064721826"
BLOCKED_OWNER_METRICOOL_BRAND_ID = "7317306"
_BLOCKED_OWNER_COMPONENTS = frozenset((
    BLOCKED_OWNER_PROFILE,
    BLOCKED_OWNER_FACEBOOK_PAGE_ID,
    BLOCKED_OWNER_METRICOOL_BRAND_ID,
))
_SAFE_POST_COMPONENT = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
DISCLOSURE_EN = "This post is required as part of my MOJ PROP challenge participation."
DISCLOSURE_FA = "این پست طبق شرایط شرکت در چالش MOJ PROP الزامی است."
ALLOWED_HOSTS = {
    "instagram": frozenset(("instagram.com", "www.instagram.com")),
    "facebook": frozenset(("facebook.com", "www.facebook.com", "m.facebook.com")),
}


def valid_platform_post_url(url, platform):
    if type(url) is not str or platform not in PLATFORMS or not 1 <= len(url) <= 512:
        return False
    try:
        u = urlsplit(url)
        host = (u.hostname or "").lower()
        raw_path = u.path
        # Percent encoding, backslashes, unicode and invisible control bytes
        # cannot transform a banned personal-page reference into valid proof.
        if (
            not raw_path or "%" in raw_path or "\\" in raw_path
            or not raw_path.isascii()
            or any(ord(ch) < 33 or ord(ch) > 126 for ch in raw_path)
        ):
            return False
        parts = raw_path.strip("/").split("/")
        if (
            u.scheme != "https" or u.netloc != host or u.username is not None
            or u.password is not None or u.port is not None
            or host not in ALLOWED_HOSTS[platform] or u.query or u.fragment
            or not parts
            or any(_SAFE_POST_COMPONENT.fullmatch(p) is None for p in parts)
            or any(p.casefold() in _BLOCKED_OWNER_COMPONENTS for p in parts)
            or BLOCKED_OWNER_PROFILE in raw_path.casefold()
            or BLOCKED_OWNER_FACEBOOK_PAGE_ID in raw_path
            or BLOCKED_OWNER_METRICOOL_BRAND_ID in raw_path
        ):
            return False
        if platform == "instagram":
            return (
                len(parts) == 2 and parts[0] in ("p", "reel")
                and re.fullmatch(r"[A-Za-z0-9_-]{4,128}", parts[1]) is not None
            )
        return (
            (len(parts) == 3 and parts[1] in ("posts", "reels", "videos"))
            or (len(parts) == 2 and parts[0] in ("posts", "reel", "videos"))
        )
    except (ValueError, AttributeError):
        return False


def aware_utc(value, field):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} requires a timezone-aware datetime")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class SocialPostingDecision:
    satisfied: bool
    required_instagram: int
    required_facebook: int
    reviewed_instagram: int
    reviewed_facebook: int
    missing_platforms: tuple[str, ...]
    challenge_ends_at: datetime
    required_visible_until: datetime
    challenge_window_complete: bool
    manual_review_required: bool = True
    automated_publishing_allowed: bool = False


def check_social_posting(*, purchase_confirmed_at, as_of, verified_posts):
    """Evaluate one retained post per network for one complete 28-day cohort.

    Trader-supplied URLs are never considered verified without an independent
    operator review, confirming actual public visibility at 28+ day maturity.
    """
    start = aware_utc(purchase_confirmed_at, "purchase_confirmed_at")
    now = aware_utc(as_of, "as_of")
    if now < start:
        raise ValueError("Assessment cannot predate confirmed purchase")
    if not isinstance(verified_posts, (tuple, list)):
        raise ValueError("Independent reviewed-post evidence list required")
    end = start + timedelta(days=DURATION_DAYS)
    accepted = set()
    maturity = {}
    for item in verified_posts:
        if not isinstance(item, dict) or set(item) != {
            "platform", "post_url", "posted_at", "reviewed_at",
            "review_status", "reviewed_by_operator", "author_verified",
            "public_visible", "disclosure_verified", "content_compliant",
            "date_verified", "continued_visibility_verified",
        }:
            continue
        platform = item["platform"]
        if platform not in PLATFORMS or not valid_platform_post_url(item["post_url"], platform):
            continue
        try:
            posted = aware_utc(item["posted_at"], "posted_at")
            reviewed = aware_utc(item["reviewed_at"], "reviewed_at")
        except ValueError:
            continue
        if not (start <= posted <= start + timedelta(hours=POST_START_GRACE_HOURS)):
            continue
        mature_at = posted + timedelta(days=DURATION_DAYS)
        if reviewed < mature_at or reviewed > now or now < end:
            continue
        if item["review_status"] != "verified" or any(item[k] is not True for k in (
            "reviewed_by_operator", "author_verified", "public_visible",
            "disclosure_verified", "content_compliant", "date_verified",
            "continued_visibility_verified",
        )):
            continue
        accepted.add(platform)
        maturity[platform] = mature_at
    missing = tuple(platform for platform in PLATFORMS if platform not in accepted)
    return SocialPostingDecision(
        satisfied=now >= end and not missing,
        required_instagram=1,
        required_facebook=1,
        reviewed_instagram=int("instagram" in accepted),
        reviewed_facebook=int("facebook" in accepted),
        missing_platforms=missing,
        challenge_ends_at=end,
        required_visible_until=max((start + timedelta(days=DURATION_DAYS), *maturity.values())),
        challenge_window_complete=now >= end,
    )
