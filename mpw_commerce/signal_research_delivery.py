"""Private research publication and buyer delivery for the single existing bot."""
import hashlib
import json
import re
from html import escape

from django.db import transaction
from django.utils import timezone

from core.canonical_content_owner import require_canonical_content_owner
from mpw_commerce.models import SignalResearchIssue
from mpw_commerce.signal_subscriptions import subscription_access, SubscriptionRejected
from services.mojtaba_signal_policy import review_signal


def publish_reviewed_issue(record, *, reviewer, source_bytes, rights_reference):
    """Authorized human-reviewed snapshot of retrieved source evidence.

    The reviewer must actually inspect the original source and its permitted
    use. This function does not independently fetch or attest provider data.
    No HTTP endpoint, email, order or automated trading is exposed here.
    """
    if (not getattr(reviewer, "is_authenticated", False)
            or not getattr(reviewer, "is_active", False)
            or not reviewer.has_perm("mpw_commerce.add_signalresearchissue")
            or record.reviewer_id != reviewer.get_username()
            or type(source_bytes) is not bytes or not 0 < len(source_bytes) <= 2_000_000
            or type(rights_reference) is not str or not 10 <= len(rights_reference.strip()) <= 250):
        raise SubscriptionRejected("Authorized source and editorial review required")
    checked = review_signal(record)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    with transaction.atomic():
        owner = require_canonical_content_owner()
        issue, _ = SignalResearchIssue.objects.get_or_create(
            record_id=record.record_id,
            defaults={"agent": owner, "reviewer": reviewer, "record": checked["record"],
                      "fingerprint": checked["evidence_fingerprint"],
                      "source_sha256": source_sha,
                      "source_rights_reference": rights_reference.strip()},
        )
        if (issue.fingerprint != checked["evidence_fingerprint"]
                or issue.record != checked["record"] or issue.agent_id != owner.pk
                or issue.reviewer_id != reviewer.pk or issue.source_sha256 != source_sha
                or issue.source_rights_reference != rights_reference.strip()):
            raise SubscriptionRejected("Previously published issue cannot be replaced")
        return issue


def private_research_html(customer, item_id):
    """Return escaped, buyer-only research from the paid coverage window.

    Never record a delivered event merely because a page was requested.
    """
    access = subscription_access(customer, item_id)
    if access is None:
        return None
    current = timezone.now()
    issues = SignalResearchIssue.objects.filter(
        agent__code="mojtaba-bot-ai", published_at__gte=access["starts_at"],
        published_at__lt=access["expires_at"], published_at__lte=current,
    ).order_by("-published_at")[:100]
    parts = [
        '<p>Prepaid educational research. No additional payment is due for this term.</p>',
        '<p>Plan: ' + escape(access["plan_id"]) + ' · Ends: '
        + escape(access["expires_at"].isoformat()) + '</p>',
    ]
    count = 0
    for issue in issues:
        doc = issue.record
        if type(doc) is not dict:
            continue
        digest = hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":"))
                                .encode("utf-8")).hexdigest()
        if (digest != issue.fingerprint or doc.get("author_agent") != "mojtaba.bot.ai"
                or doc.get("record_id") != issue.record_id
                or not re.fullmatch(r"[0-9a-f]{64}", issue.source_sha256)):
            continue
        fields = ("asset", "as_of", "scenario", "invalidation", "risk_statement", "evidence_url")
        if any(type(doc.get(key)) is not str for key in fields):
            continue
        parts.append("<article><h2>" + escape(doc["asset"]) + "</h2>"
                     + "".join("<p>" + escape(doc[key]) + "</p>" for key in fields[1:])
                     + "</article>")
        count += 1
    if not count:
        parts.append("<p>No reviewed research has been published for this coverage period yet. "
                     "Contact purchase support; do not pay again.</p>")
    return "".join(parts)
