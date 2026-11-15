"""Offline private social proof workflow for a single 28-day paid challenge.

No Meta account credentials, automated publishing or public evidence intake
endpoint. A trusted settled purchase is required before URL submission.
"""
from datetime import timedelta
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone as django_timezone

from .models import PropAccount, PropSocialEvidence
from .social_policy import (
    NEW_CONTRACT_VERSION, DURATION_DAYS, POST_START_GRACE_HOURS,
    aware_utc, valid_platform_post_url,
)


class SocialEvidenceRejected(ValueError):
    pass


@transaction.atomic
def submit_social_evidence(*, account_id, submitter, platform,
                           post_url, posted_at, explicit_consent=False):
    """Record ONE pending platform link for a confirmed challenge purchase."""
    if not submitter or submitter.is_authenticated is not True or explicit_consent is not True:
        raise PermissionDenied("Trader login and informed consent are required")
    account = (
        PropAccount.objects.select_for_update().select_related(
            "trader", "challenge_enrollment"
        ).get(pk=account_id)
    )
    if account.trader.user_id != submitter.pk:
        raise PermissionDenied("Foreign account evidence is forbidden")
    purchase = account.challenge_enrollment
    if (not purchase or purchase.trader_id != account.trader_id
            or purchase.settlement_verified is not True
            or purchase.terms_version != NEW_CONTRACT_VERSION
            or account.policy_version != NEW_CONTRACT_VERSION):
        raise SocialEvidenceRejected("Trusted settled prospective purchase required")
    if account.kind not in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
        raise SocialEvidenceRejected("Only simulation challenge accounts accept social proof")
    if account.status not in (PropAccount.Status.WAITING, PropAccount.Status.ACTIVE):
        raise SocialEvidenceRejected("Challenge account is not active")
    if not valid_platform_post_url(post_url, platform):
        raise SocialEvidenceRejected("Unsupported post URL or blocked account")
    submitted_at = aware_utc(posted_at, "posted_at")
    start = aware_utc(purchase.confirmed_at, "confirmed_at")
    if (submitted_at < start
            or submitted_at > start + timedelta(hours=POST_START_GRACE_HOURS)
            or submitted_at > django_timezone.now()):
        raise SocialEvidenceRejected("Post must be published within the first 24 hours")
    if PropSocialEvidence.objects.filter(enrollment=purchase, platform=platform).exists():
        raise SocialEvidenceRejected("One post per platform for entire purchase already exists")
    record = PropSocialEvidence(
        account=account, enrollment=purchase, platform=platform,
        post_url=post_url, posted_at=submitted_at,
    )
    record.save()
    return record


@transaction.atomic
def review_social_evidence(*, evidence_id, reviewer, audited_facts, reviewed_at=None):
    """Independent human verifies original post still public after four weeks."""
    if (
        not reviewer or reviewer.is_authenticated is not True
        or reviewer.is_active is not True or reviewer.is_staff is not True
    ):
        raise PermissionDenied("Active independent staff role required")
    fields = {
        "author_verified", "public_visible", "disclosure_verified",
        "content_compliant", "date_verified", "continued_visibility_verified",
    }
    if not isinstance(audited_facts, dict) or set(audited_facts) != fields:
        raise SocialEvidenceRejected("All six manually reviewed facts required")
    row = (
        PropSocialEvidence.objects.select_for_update().select_related(
            "account__trader", "enrollment",
        ).get(pk=evidence_id)
    )
    if reviewer.pk == row.account.trader.user_id:
        raise PermissionDenied("A participant may not approve their own post")
    if row.review_status != PropSocialEvidence.Review.PENDING:
        raise SocialEvidenceRejected("Final proof decisions cannot be overwritten")
    now = django_timezone.now() if reviewed_at is None else aware_utc(reviewed_at, "reviewed_at")
    if (now > django_timezone.now()
            or now < row.posted_at + timedelta(days=DURATION_DAYS)
            or row.enrollment.settlement_verified is not True):
        raise SocialEvidenceRejected("28-day publication lifetime not yet independently provable")
    valid = all(audited_facts[key] is True for key in fields)
    row.review_status = (
        PropSocialEvidence.Review.VERIFIED if valid
        else PropSocialEvidence.Review.REJECTED
    )
    row.reviewed_by = reviewer
    row.reviewed_at = now
    for key in fields:
        setattr(row, key, audited_facts[key] is True)
    row.save()
    return row
