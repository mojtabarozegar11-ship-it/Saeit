"""Buyer-held receipt credentials for Moj Prop manual review, never a paid order.

This avoids publishing private client details or issuing insecure public URLs.
No customer email, wallet, notes, or personally identifiable information is
included in the signed bearer token.
"""
from django.core import signing

RECEIPT_SALT = "mojprop-review-receipt-v1"
RECEIPT_AGE_SECONDS = 90 * 24 * 60 * 60

PUBLIC_STATUSES = {
    "new": "Received for manual review",
    "reviewing": "Being reviewed",
    "offer_sent": "Written offer recorded; customer receipt not verified",
    "approved": "Scope accepted; delivery pending",
    "delivered": "Delivery marked complete",
    "closed": "Request closed",
    "spam": "Request closed",
}


def make_receipt_token(request_id: str) -> str:
    if not isinstance(request_id, str) or not request_id.startswith("MOJPROP-"):
        raise ValueError("Not a Moj Prop request")
    return signing.TimestampSigner(salt=RECEIPT_SALT).sign(request_id)


def verify_receipt_token(token: str) -> str | None:
    if not isinstance(token, str) or len(token) > 256:
        return None
    try:
        request_id = signing.TimestampSigner(salt=RECEIPT_SALT).unsign(
            token, max_age=RECEIPT_AGE_SECONDS
        )
    except signing.BadSignature:
        return None
    return request_id if request_id.startswith("MOJPROP-") else None


def public_status_text(status: str) -> str:
    return PUBLIC_STATUSES.get(status, "Unavailable")
