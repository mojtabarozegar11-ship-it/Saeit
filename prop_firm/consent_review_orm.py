"""Private read-only ORM adapter for the existing MOJ-PROP-01 review bridge.

This module never accepts a public email as proof of identity and never creates
an invoice, enrollment, payment, account, or marketing permission.
"""
from hashlib import sha256
import hmac

from django.db import transaction

from .consent_review_bridge import BridgeClosed, prepare_consent_review
from .lead_models import PropInterest
from .order_readiness import SKU


def review_existing_interest(*, interest_pk, authenticated_buyer_ref,
                             independently_verified_interest_pk,
                             independent_buyer_link_verified,
                             signed_customer_terms_sha256,
                             trusted_contract_sha256,
                             trusted_gate_evidence):
    """Produce a private review only after independent buyer binding.

    Callers must independently authenticate buyer, validate KYC and signed
    customer terms, and populate trusted gates from private verified records.
    A database lead or an email is never sufficient.
    """
    if type(interest_pk) is not int or interest_pk <= 0:
        raise BridgeClosed("invalid interest identifier")
    if (type(independently_verified_interest_pk) is not int
            or independently_verified_interest_pk != interest_pk):
        raise BridgeClosed("unverified buyer-to-interest reference")
    if independent_buyer_link_verified is not True:
        raise BridgeClosed("independent buyer binding missing")
    if type(authenticated_buyer_ref) is not str:
        raise BridgeClosed("authenticated buyer reference missing")
    # Atomic snapshot prevents a withdrawn record being accepted between
    # the consent check and provenance calculation. No rows are mutated.
    with transaction.atomic():
        lead = (PropInterest.objects.select_for_update()
                .filter(pk=interest_pk).first())
        if lead is None:
            raise BridgeClosed("interest not found")
        if lead.status == "withdrawn":
            raise BridgeClosed("consent withdrawn")
        if lead.status not in ("new", "contacted"):
            raise BridgeClosed("unsupported consent state")
        if lead.plan_code != SKU:
            raise BridgeClosed("not the real Plan 1 SKU")
        if lead.consent_version != "moj-prop-interest-v1":
            raise BridgeClosed("unknown consent provenance")
        # Digest intentionally excludes email/PII; it identifies the immutable
        # consent-origin tuple, not a signature or legal acceptance.
        origin = f"{lead.pk}|{lead.plan_code}|{lead.consent_version}|{lead.created_at.isoformat()}"
        digest = sha256(origin.encode("utf-8")).hexdigest()
        result = prepare_consent_review(
            interest_ref=str(lead.pk),
            interest_digest=digest,
            buyer_ref=authenticated_buyer_ref,
            consent_recorded=True,
            independent_buyer_link_verified=True,
            signed_customer_terms_sha256=signed_customer_terms_sha256,
            trusted_contract_sha256=trusted_contract_sha256,
            trusted_gate_evidence=trusted_gate_evidence,
        )
        if result.invoice_authorized or result.payment_authorized or result.enrollment_authorized:
            raise BridgeClosed("review must never grant purchase authority")
        return result
