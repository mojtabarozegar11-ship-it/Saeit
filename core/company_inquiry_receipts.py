"""Unforgeable, short-lived status receipts for existing company CRM leads.

No customer identity, email, message, phone or money moves into the URL.
Signed receipts only reveal a coarse workflow state and are not contracts.
"""
from django.core import signing
from django.http import Http404

_SALT = "core.company-inquiry.receipt.v1"
_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def issue_receipt(inquiry_id):
    if type(inquiry_id) is not int or inquiry_id < 1:
        raise ValueError("Invalid inquiry identifier")
    return signing.dumps({"v": 1, "id": inquiry_id}, salt=_SALT)


def verify_receipt(token):
    if type(token) is not str or not 1 <= len(token) <= 350:
        raise Http404("Invalid or expired inquiry receipt")
    try:
        payload = signing.loads(token, salt=_SALT, max_age=_MAX_AGE_SECONDS)
    except signing.BadSignature as exc:
        raise Http404("Invalid or expired inquiry receipt") from exc
    if (type(payload) is not dict or payload.get("v") != 1
            or type(payload.get("id")) is not int or payload["id"] < 1
            or set(payload) != {"v", "id"}):
        raise Http404("Invalid or expired inquiry receipt")
    return payload["id"]
