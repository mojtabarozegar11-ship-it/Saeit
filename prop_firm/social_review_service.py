"""Staff-reviewed social evidence staging. Never publishes, advertises or buys.

The trader supplies their own existing public post URLs only after explicitly
accepting the contract. A separate staff member must inspect each live link
and attest author/date/advertising disclosure/content. No Meta API tokens or
account access is requested, and no Instagram/Facebook write endpoint exists.
"""
from datetime import datetime, time, timedelta, timezone

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone as django_timezone

from .models import PropAccount, PropExecution, PropSocialEvidence
from .social_policy import NEW_CONTRACT_VERSION, utc_day, valid_platform_post_url


class SocialEvidenceRejected(ValueError):
    pass


def _verified_trade_on(account, trading_day):
    start = datetime.combine(trading_day, time.min, tzinfo=timezone.utc)
    return PropExecution.objects.filter(
        account=account,
        reconciliation_status="verified",
        closed_at__gte=start, closed_at__lt=start + timedelta(days=1),
    ).exists()


@transaction.atomic
def submit_social_evidence(*, account_id, submitter, trading_day,
                           platform, post_url, posted_at, explicit_consent=False):
    """Store a pending URL privately, without granting a passed challenge."""
    if (not submitter or not submitter.is_authenticated or explicit_consent is not True):
        raise PermissionDenied("Trader login and informed social-post consent are required")
    account = PropAccount.objects.select_for_update().select_related("trader").get(pk=account_id)
    if account.trader.user_id != submitter.pk:
        raise PermissionDenied("Cannot submit proof to another trader's account")
    if account.policy_version != NEW_CONTRACT_VERSION:
        raise SocialEvidenceRejected("Older contracts cannot acquire this condition retroactively")
    if account.kind not in (PropAccount.Kind.PHASE_ONE, PropAccount.Kind.PHASE_TWO):
        raise SocialEvidenceRejected("Only active simulated challenge phases qualify")
    if account.status not in (PropAccount.Status.WAITING, PropAccount.Status.ACTIVE):
        raise SocialEvidenceRejected("Account is no longer accepting social evidence")
    if not valid_platform_post_url(post_url, platform):
        raise SocialEvidenceRejected("Unsupported post URL or platform")
    if posted_at > django_timezone.now():
        raise SocialEvidenceRejected("Future social publications cannot be evidence")
    if utc_day(posted_at) != trading_day or not _verified_trade_on(account, trading_day):
        raise SocialEvidenceRejected("One post must match a verified UTC trading day")
    if PropSocialEvidence.objects.filter(
        account=account, trading_day=trading_day, platform=platform
    ).exists():
        raise SocialEvidenceRejected("Proof already staged for this platform and trading day")
    row = PropSocialEvidence(
        account=account, trading_day=trading_day, platform=platform,
        post_url=post_url, posted_at=posted_at,
    )
    row.save()
    return row


@transaction.atomic
def review_social_evidence(*, evidence_id, reviewer, audited_facts,
                           reviewed_at=None):
    """Human-controlled review; no links are opened or posted by this service."""
    if not reviewer or reviewer.is_authenticated is not True or reviewer.is_staff is not True:
        raise PermissionDenied("Only independent staff may review social evidence")
    if not isinstance(audited_facts, dict) or set(audited_facts) != {
        "author_verified", "public_visible", "disclosure_verified",
        "content_compliant", "date_verified",
    }:
        raise SocialEvidenceRejected("Complete manual review facts are required")
    row = PropSocialEvidence.objects.select_for_update().select_related(
        "account__trader", "reviewed_by"
    ).get(pk=evidence_id)
    if reviewer.pk == row.account.trader.user_id:
        raise PermissionDenied("Self-verification forbidden")
    if row.review_status != PropSocialEvidence.Review.PENDING:
        raise SocialEvidenceRejected("Reviewed evidence cannot be silently overwritten")
    if not _verified_trade_on(row.account, row.trading_day):
        raise SocialEvidenceRejected("Trading day has lost verified status")
    now = django_timezone.now() if reviewed_at is None else reviewed_at
    if (now.tzinfo is None or now.utcoffset() is None
            or now < row.posted_at or now > django_timezone.now()):
        raise SocialEvidenceRejected("Review time must be valid and after publication")
    all_checked = all(value is True for value in audited_facts.values())
    row.review_status = (
        PropSocialEvidence.Review.VERIFIED if all_checked
        else PropSocialEvidence.Review.REJECTED
    )
    row.reviewed_by = reviewer
    row.reviewed_at = now
    for field, value in audited_facts.items():
        setattr(row, field, value is True)
    row.save()
    return row
