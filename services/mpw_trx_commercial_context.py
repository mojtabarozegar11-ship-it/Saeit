"""Minimal customer-facing TRX feature switch; no network or database access."""
from __future__ import annotations


def checkout_flags(request):
    from django.conf import settings
    from services.mpw_walletless_commercial_intent import public_release_authorized
    try:
        host=request.get_host().split(":")[0].lower()
    except Exception:
        host=""
    released=bool(
        host in ("mojplaywin.com","www.mojplaywin.com")
        and request.is_secure()
        and getattr(settings,"MPW_WALLETLESS_TRX_PUBLIC_ENABLED",False) is True
        and public_release_authorized(settings)
    )
    return {"mpw_trx_easy_enabled":released}


def _sha256_hex(value):
    return (type(value) is str and len(value)==64
            and all(character in "0123456789abcdef" for character in value.lower()))


def rights_cleared_for_sale(product):
    """Validate declared approval and exact artifact/document digest linkage.

    This is a metadata consistency gate, NOT independent legal certification.
    It must not be used to generate, infer, or set any approval flags.
    """
    metadata=getattr(product,"metadata",None)
    if type(metadata) is not dict:
        return False
    if (metadata.get("rights_cleared") is not True
            or metadata.get("publication_approved") is not True):
        return False
    catalog_sha=metadata.get("sha256")
    rights_sha=metadata.get("rights_asset_sha256")
    document_sha=metadata.get("rights_document_sha256")
    return (_sha256_hex(catalog_sha)
            and _sha256_hex(rights_sha)
            and _sha256_hex(document_sha)
            and catalog_sha.lower()==rights_sha.lower())
