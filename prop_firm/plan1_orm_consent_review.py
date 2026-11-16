"""Cycle B: authenticated ORM-to-private-review adapter; strictly no commerce.

Only an already authenticated staff service may invoke this function. It reads
the current canonical PropInterest row; it does not create a second lead,
alter consent, persist PII, issue an invoice or authorize contact.
"""
from __future__ import annotations

from django.db import transaction

from .lead_models import PropInterest
from .plan1_canonical_interest_bridge import (
    bind_canonical_interest_to_private_inquiry,
    match_private_review_to_canonical_interest,
)
from .buyer_order_review import Plan1OrderGateClosed


def review_existing_interest(*, actor, interest_pk, inquiry, consent_attestation,
                             consent_tag_hex, consent_key, request_ref,
                             inquiry_sha256, consent_evidence_sha256,
                             private_order_draft):
    """Return a PII-free consent link, not an enrollment or payment approval.

    An external, trusted consent registry supplies the HMAC attestation. This
    method does not fabricate consent or accept unsigned browser submissions.
    The caller must recheck withdrawal immediately before any later contact.
    """
    if (actor is None or not getattr(actor, "is_authenticated", False)
            or not getattr(actor, "is_active", False)
            or not getattr(actor, "is_staff", False)):
        raise Plan1OrderGateClosed("authenticated authorized staff required")
    if type(interest_pk) is not int or interest_pk <= 0:
        raise Plan1OrderGateClosed("invalid canonical interest identifier")
    with transaction.atomic():
        row = (PropInterest.objects.select_for_update()
               .filter(pk=interest_pk).values(
                   "id", "email", "plan_code", "consent_version",
                   "source_language", "status").first())
        if row is None:
            raise Plan1OrderGateClosed("canonical consent record unavailable")
        link = bind_canonical_interest_to_private_inquiry(
            canonical_interest=row, inquiry=inquiry,
            trusted_consent_attestation=consent_attestation,
            signed_consent_tag_hex=consent_tag_hex,
            trusted_consent_key=consent_key,
            expected_request_ref=request_ref,
            expected_interest_pk=interest_pk,
            expected_inquiry_sha256=inquiry_sha256,
            expected_consent_evidence_sha256=consent_evidence_sha256,
        )
        return match_private_review_to_canonical_interest(
            consent_link=link, private_order_draft=private_order_draft)
