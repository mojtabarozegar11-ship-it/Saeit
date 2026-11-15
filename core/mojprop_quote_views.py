"""Buyer-facing, time-limited written proposal lookup.

There is no invoice creation, email delivery or payment action here.
A proposal may be read only with a signed short-lived token and an
independently enabled public-release setting. The URL is a bearer secret.
"""
from django.conf import settings
from django.core import signing
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.models import MojPropOffer
from core.mojprop_quote_contract import QuoteContractError, validate_acceptance_reference

SALT = "mojprop.quote.read.v1"
MAX_AGE_SECONDS = 24 * 3600
PUBLIC_HOSTS = frozenset((
    "mojplaywin.com", "www.mojplaywin.com",
    "zomorodmelal.ir", "www.zomorodmelal.ir",
))


def _accepted_offer_evidence_is_safe(offer):
    if (offer.accepted_at is None
            or offer.accepted_at < offer.issued_at
            or offer.accepted_at >= offer.expires_at
            or offer.accepted_at > timezone.now()):
        return False
    try:
        validate_acceptance_reference(offer.acceptance_reference)
    except (QuoteContractError, AttributeError, TypeError):
        return False
    return True


def quote_read_token(offer):
    """Use only for an already issued, unexpired, reviewed written quote."""
    if (type(offer) is not MojPropOffer
            or offer.pk is None or offer.status not in ("issued", "accepted")
            or offer.issued_at is None or offer.expires_at is None
            or offer.reviewed_at is None or offer.reviewed_at > offer.issued_at
            or offer.expires_at <= timezone.now()
            or offer.issued_at > timezone.now()
            or (offer.status == "accepted"
                and not _accepted_offer_evidence_is_safe(offer))):
        raise ValueError("quote is not available for buyer review")
    if MojPropOffer.objects.filter(
        lead_id=offer.lead_id, version__gt=offer.version,
        status__in=("issued", "accepted"),
        issued_at__isnull=False,
    ).exists():
        raise ValueError("a newer written proposal superseded this offer")
    return signing.dumps(
        {"pk": offer.pk, "version": offer.version},
        salt=SALT, compress=False,
    )


@require_GET
@never_cache
def customer_quote(request, token):
    if (getattr(settings, "MOJPROP_PUBLIC_QUOTES_ENABLED", False) is not True
            or not request.is_secure()
            or request.get_host().split(":")[0].lower() not in PUBLIC_HOSTS):
        raise Http404
    if type(token) is not str or len(token) > 700:
        raise Http404
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
        if (type(data) is not dict or set(data) != {"pk", "version"}
                or type(data["pk"]) is not int or data["pk"] < 1
                or type(data["version"]) is not int or data["version"] < 1):
            raise Http404
        offer = MojPropOffer.objects.select_related("lead").filter(
            pk=data["pk"], version=data["version"],
            status__in=("issued", "accepted"),
            issued_at__isnull=False,
            expires_at__gt=timezone.now(),
        ).first()
        if (offer is None or offer.reviewed_at is None
                or offer.reviewed_at > offer.issued_at
                or offer.issued_at > timezone.now()
                or (offer.status == "accepted"
                    and (offer.accepted_at is None
                         or offer.accepted_at < offer.issued_at
                         or offer.accepted_at >= offer.expires_at
                         or offer.accepted_at > timezone.now()
                         or not isinstance(offer.acceptance_reference, str)
                         or not offer.acceptance_reference.strip()))
                or MojPropOffer.objects.filter(
                    lead_id=offer.lead_id, version__gt=offer.version,
                    status__in=("issued", "accepted"),
                    issued_at__isnull=False,
                ).exists()):
            raise Http404
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        raise Http404 from None
    # This intentionally excludes name, email, internal notes and IP metadata.
    response = HttpResponse(
        offer.manual_quote_text,
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
