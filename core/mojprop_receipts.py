"""Buyer-held signed manual-review receipt, not a paid invoice or entitlement.

There is deliberately no PII in the signed token. A bearer receipt is private
and time-limited; callers must not mistake a lead-stage label for settlement,
accepted contract terms, a completed delivery or evidence of refund.
"""
import re

from django.core import signing

RECEIPT_SALT = "mojprop-review-receipt-v1"
RECEIPT_AGE_SECONDS = 90 * 24 * 60 * 60
# Retain all old signed receipts while accepting the HMAC-derived, DB-unique
# UUIDv4 replay identifier. Neither format embeds buyer identity or a key.
RECEIPT_ID = re.compile(r"(?:MOJPROP-[0-9]{8}-[0-9A-F]{8}|MOJPROP-ID-[0-9A-F]{24})\Z")
MAX_TOKEN_CHARS = 256

PUBLIC_STATUSES = {
    "new": "Received for manual review; no payment collected",
    "reviewing": "Being reviewed; no payment collected",
    "offer_sent": "Written offer recorded; settlement requires separate verification",
    "approved": "Manual scoping approved; settlement requires separate verification",
    "delivered": "Delivery stage recorded; independently verify customer receipt",
    "closed": "Request closed; financial status is not assessed by this receipt",
    "spam": "Request closed",
}


def valid_request_id(request_id):
    return (type(request_id) is str
            and RECEIPT_ID.fullmatch(request_id) is not None)


def make_receipt_token(request_id: str) -> str:
    if not valid_request_id(request_id):
        raise ValueError("invalid Moj Prop request ID")
    return signing.TimestampSigner(salt=RECEIPT_SALT).sign(request_id)


def verify_receipt_token(token: str) -> str | None:
    if (type(token) is not str or not token
            or len(token) > MAX_TOKEN_CHARS
            or any(ord(ch) < 33 or ord(ch) > 126 for ch in token)):
        return None
    try:
        request_id = signing.TimestampSigner(salt=RECEIPT_SALT).unsign(
            token, max_age=RECEIPT_AGE_SECONDS
        )
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
    return request_id if valid_request_id(request_id) else None


def public_status_text(status: str) -> str:
    if type(status) is not str:
        return "Unavailable"
    return PUBLIC_STATUSES.get(status, "Unavailable")
