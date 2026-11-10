"""Source-only operational rights review gate for NEW guest TRX sales.

A flag is not a copyright certificate. The independent review must verify
the exact deliverable and commercial distribution rights before these fields
may legitimately be set. Never apply this to paid-order recovery or download.
"""

NEW_SALE_SKUS = frozenset((72, 225, 879))
REQUIRED_FLAGS = (
    "asset_verified",
    "license_verified",
    "quality_approved",
    "factory_publication_permission",
    "checkout_enabled",
    "rights_cleared",
    "publication_approved",
)


def reviewed_for_new_sale(product):
    """Refuse missing, self-contradictory or unreviewed catalog metadata."""
    if getattr(product, "pk", None) not in NEW_SALE_SKUS:
        return False
    if getattr(product, "active", None) is not True:
        return False
    metadata = getattr(product, "metadata", None)
    if type(metadata) is not dict:
        return False
    if metadata.get("rights_review_status") != "independently_cleared":
        return False
    return all(metadata.get(flag) is True for flag in REQUIRED_FLAGS)
