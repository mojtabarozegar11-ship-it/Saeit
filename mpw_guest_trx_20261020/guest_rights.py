"""Fail-closed legal-release guard for NEW MojPlayWin guest invoices only.

Never import this in existing paid-order receipt or download handlers. A catalog
metadata flag is not a copyright certificate; it is an operational release gate
that may be set only after independent documentary rights review.
"""

NEW_BOOK_SKUS = frozenset((72, 225))
REQUIRED_RELEASE_FLAGS = (
    "asset_verified",
    "license_verified",
    "quality_approved",
    "factory_publication_permission",
    "checkout_enabled",
)


def may_start_new_order(product):
    """True only for a source-approved book with explicit independent rights status."""
    if getattr(product, "pk", None) not in NEW_BOOK_SKUS:
        return False
    if getattr(product, "active", None) is not True:
        return False
    metadata = getattr(product, "metadata", None)
    if type(metadata) is not dict:
        return False
    if metadata.get("rights_review_status") != "independently_cleared":
        return False
    return all(metadata.get(flag) is True for flag in REQUIRED_RELEASE_FLAGS)
