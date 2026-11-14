"""New-cohort MOJ PROP social posting condition (proposed, not yet sold).

One independently reviewed Instagram post AND one independently reviewed
Facebook post for each *verified UTC trading date*, separately for each
simulated challenge phase. Trading-day counts arise solely from reconciled
broker/simulator executions; no fabricated public endorsements or automated
posting are allowed. Historical cohorts remain under their existing contract.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlsplit

PLATFORMS = ("instagram", "facebook")
DISCLOSURE_EN = "This post is required as part of my MOJ PROP trading challenge."
DISCLOSURE_FA = "این پست طبق شرایط چالش معاملاتی MOJ PROP منتشر شده است."
BLOCKED_OWNER_PROFILE = "dr.mojtaba.rozegar"
LEGACY_CONTRACT_VERSION = "2026-11-14/v1.1"
NEW_CONTRACT_VERSION = "2026-11-15/v1.2"

ALLOWED_HOSTS = {
    "instagram": frozenset(("instagram.com", "www.instagram.com")),
    "facebook": frozenset(("facebook.com", "www.facebook.com", "m.facebook.com")),
}


def valid_platform_post_url(url, platform):
    """Accept only a platform's HTTPS post/reel URL, not a profile or shortener."""
    if type(url) is not str or platform not in PLATFORMS:
        return False
    if not 1 <= len(url) <= 512:
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/")
        parts = path.split("/")
        if (
            parsed.scheme != "https" or parsed.netloc != host
            or parsed.username is not None or parsed.password is not None
            or host not in ALLOWED_HOSTS[platform]
            or parsed.query or parsed.fragment
            or not path or BLOCKED_OWNER_PROFILE in path.lower()
        ):
            return False
        if platform == "instagram":
            return len(parts) == 2 and parts[0] in ("p", "reel") and bool(parts[1])
        # Facebook uses several public post URL shapes; human review still
        # confirms the actual post owner and public visibility.
        return (
            (len(parts) >= 3 and parts[0] in ("posts", "reel", "videos"))
            or (len(parts) >= 2 and parts[1] in ("posts", "reels", "videos"))
            or (len(parts) >= 2 and parts[0] in ("permalink", "story.php"))
        )
    except (ValueError, AttributeError):
        return False


def utc_day(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Verified trade and post times require aware UTC datetimes")
    return value.astimezone(timezone.utc).date()


@dataclass(frozen=True)
class SocialPostingDecision:
    satisfied: bool
    trading_days: int
    required_instagram: int
    required_facebook: int
    reviewed_instagram: int
    reviewed_facebook: int
    missing_days: tuple[str, ...]
    manual_review_required: bool = True
    automated_publishing_allowed: bool = False


def check_social_posting(*, verified_trading_dates, verified_posts):
    """Business assessment over *already audited* trading days and posts.

    Evidence needs both platforms on the same UTC trading date. The review
    process must independently attest the post's date, author, commercial
    disclosure, publicity and content; merely submitting a URL never passes.
    """
    if not isinstance(verified_trading_dates, (set, frozenset, tuple, list)):
        raise ValueError("Authoritative trading dates required")
    dates = set(verified_trading_dates)
    if any(type(x) is not date for x in dates):
        raise ValueError("Trading dates must be UTC calendar-date values")
    if not isinstance(verified_posts, (tuple, list)):
        raise ValueError("Reviewed evidence list required")
    accepted = set()
    for item in verified_posts:
        if not isinstance(item, dict) or set(item) != {
            "trading_day", "platform", "post_url", "review_status",
            "reviewed_by_operator", "author_verified", "public_visible",
            "disclosure_verified", "content_compliant", "date_verified",
        }:
            continue
        day, platform = item["trading_day"], item["platform"]
        if (type(day) is not date or day not in dates
                or platform not in PLATFORMS
                or item["review_status"] != "verified"
                or not valid_platform_post_url(item["post_url"], platform)
                or any(item[key] is not True for key in (
                    "reviewed_by_operator", "author_verified", "public_visible",
                    "disclosure_verified", "content_compliant", "date_verified",
                ))):
            continue
        accepted.add((day, platform))
    missing = tuple(
        f"{day.isoformat()}:{platform}"
        for day in sorted(dates) for platform in PLATFORMS
        if (day, platform) not in accepted
    )
    return SocialPostingDecision(
        satisfied=bool(dates) and not missing,
        trading_days=len(dates),
        required_instagram=len(dates),
        required_facebook=len(dates),
        reviewed_instagram=sum((day, "instagram") in accepted for day in dates),
        reviewed_facebook=sum((day, "facebook") in accepted for day in dates),
        missing_days=missing,
    )
