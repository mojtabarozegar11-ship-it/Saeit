"""Read-only mathematics for one qualifying Instagram OR Facebook post, 28 days.

This module cannot verify ownership, visibility, a signed source or whether
mandatory endorsement is lawful. Snapshot timestamps alone can be forged.
NO purchases, marketing approval, funded accounts, live orders or payouts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .plan1_v14_social_or_50_terms import SOCIAL_DURATION_HOURS, SOCIAL_PLATFORMS

DURATION = timedelta(hours=SOCIAL_DURATION_HOURS)
MAX_OBSERVATION_GAP = timedelta(hours=24)
FIRST_SNAPSHOT_DELAY = timedelta(hours=1)
MAX_OBSERVATIONS = 256
BLOCKED_OWNER_PROFILE = "dr.mojtaba.rozegar"


@dataclass(frozen=True)
class SocialPostClaim:
    platform: str
    url: str
    published_at: datetime
    public_visibility_snapshots: tuple[datetime, ...]
    is_original_claimed: bool
    participation_disclosure_claimed: bool
    participant_is_not_owner_claimed: bool


@dataclass(frozen=True)
class Social28DayReview:
    candidate_platform: str
    observed_hours: int
    observations: int
    reasons: tuple[str, ...]
    timeline_mathematically_consistent: bool
    social_post_independently_verified: bool = False
    legal_approval_verified: bool = False
    terms_signed: bool = False
    customer_checkout_authorized: bool = False
    customer_enrollment_authorized: bool = False
    broker_live_orders_authorized: bool = False
    payout_authorized: bool = False


def _utc(value, name):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(name + " must be timezone-aware")
    return value.astimezone(timezone.utc)


def _post_url_valid(platform, text):
    if type(text) is not str or not 1 <= len(text) <= 512:
        return False
    try:
        u = urlsplit(text)
        host = (u.hostname or "").lower()
        if (u.scheme != "https" or u.username is not None or u.password is not None
                or u.port is not None or u.netloc != host
                or u.query or u.fragment):
            return False
        path = tuple(p for p in u.path.strip("/").split("/") if p)
        if platform == "instagram":
            return (host in {"instagram.com", "www.instagram.com"}
                    and len(path) == 2 and path[0] in {"p", "reel"}
                    and len(path[1]) >= 3)
        if platform == "facebook":
            return (host in {"facebook.com", "www.facebook.com", "m.facebook.com"}
                    and len(path) == 3 and path[1] in {"posts", "videos"}
                    and len(path[0]) >= 2 and len(path[2]) >= 3
                    and path[0].lower() != BLOCKED_OWNER_PROFILE)
    except (TypeError, ValueError):
        return False
    return False


def review_social_post_28d(claim: SocialPostClaim, *, now: datetime) -> Social28DayReview:
    """Review a single nominated qualifying post (NOT all voluntary posts)."""
    if type(claim) is not SocialPostClaim:
        raise ValueError("typed social claim required")
    at = _utc(now, "assessment timestamp")
    published = _utc(claim.published_at, "publication timestamp")
    snap = claim.public_visibility_snapshots
    if type(snap) is not tuple or not 1 <= len(snap) <= MAX_OBSERVATIONS:
        raise ValueError("bounded immutable visibility observations required")
    stamps = tuple(_utc(d, "observation timestamp") for d in snap)
    reasons = []
    if claim.platform not in SOCIAL_PLATFORMS or not _post_url_valid(claim.platform, claim.url):
        reasons.append("unsupported_or_unsafe_post_url")
    if claim.is_original_claimed is not True:
        reasons.append("post_originality_not_claimed")
    if claim.participation_disclosure_claimed is not True:
        reasons.append("participant_relationship_not_disclosed")
    if claim.participant_is_not_owner_claimed is not True:
        reasons.append("owner_account_post_forbidden")
    if published > at:
        reasons.append("publication_in_future")
    if at - published < DURATION:
        reasons.append("twenty_eight_full_days_not_elapsed")
    if not published <= stamps[0] <= published + FIRST_SNAPSHOT_DELAY:
        reasons.append("initial_visibility_not_observed")
    if stamps[-1] < published + DURATION or stamps[-1] > at:
        reasons.append("end_of_visibility_not_observed")
    if any(not a < b or b - a > MAX_OBSERVATION_GAP for a, b in zip(stamps, stamps[1:])):
        reasons.append("daily_visibility_evidence_has_gap_or_replay")
    if any(t < published or t > at for t in stamps):
        reasons.append("observation_outside_publication_and_now")
    hours = max(0, int((stamps[-1] - stamps[0]).total_seconds() // 3600))
    return Social28DayReview(
        candidate_platform=claim.platform,
        observed_hours=hours,
        observations=len(stamps),
        reasons=tuple(dict.fromkeys(reasons)),
        timeline_mathematically_consistent=not reasons,
    )
