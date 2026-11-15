"""Transactionally durable pending orders for authorized internal service callers.

Only server-owned, previously approved route/offer objects may be passed in.
No browser request, settlement flag, trading signal, or payment operation
is authorized by this module. The row's integrity is rechecked at every read.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import re

from django.db import transaction

from core.mojtaba_signal_order_contract import build_pending_order_record
from core.mojtaba_signal_order_ledger import PendingOrderReceipt
from .models import PendingSignalOrderRecord


_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class DurableSignalOrderError(ValueError):
    pass


def _digest(record: dict) -> str:
    if type(record) is not dict:
        raise DurableSignalOrderError("canonical_pending_record_required")
    try:
        canonical = json.dumps(
            record, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise DurableSignalOrderError("pending_record_not_json_safe") from exc
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _check_row(row):
    if (type(row.payload) is not dict
            or row.payload.get("order_id") != row.order_id
            or row.payload.get("tenant_id") != row.tenant_id
            or row.payload.get("offer_id") != row.offer_id
            or row.payload.get("state") != "awaiting_external_settlement"
            or row.payload.get("settlement_verified") is not False
            or row.payload.get("entitlement_granted") is not False
            or row.payload.get("delivery_verified") is not False
            or row.payload.get("receipt_issued") is not False
            or row.payload.get("financial_signal") is not False
            or row.payload.get("payment_required") is not True
            or type(row.payload_digest) is not str
            or not hmac.compare_digest(row.payload_digest, _digest(row.payload))):
        raise DurableSignalOrderError("stored_order_integrity_invalid")
    return deepcopy(row.payload)


@transaction.atomic
def persist_pending_order(intent, trusted_route, trusted_offer, *, now=None):
    """Unique DB-backed idempotency across workers and process restarts.

    Does not create a TRX invoice; does not grant paid entitlement.
    """
    pending = build_pending_order_record(
        intent, trusted_route, trusted_offer, now=now,
    )
    fingerprint = _digest(pending)
    row, created = PendingSignalOrderRecord.objects.get_or_create(
        order_id=pending["order_id"],
        defaults={
            "tenant_id": pending["tenant_id"],
            "offer_id": pending["offer_id"],
            "payload": pending,
            "payload_digest": fingerprint,
        },
    )
    stored = _check_row(row)
    if (row.tenant_id != pending["tenant_id"]
            or row.offer_id != pending["offer_id"]
            or stored != pending
            or not hmac.compare_digest(row.payload_digest, fingerprint)):
        raise DurableSignalOrderError("order_id_conflict")
    return PendingOrderReceipt(
        order_id=row.order_id, created=created, record=stored,
    )


def read_pending_order(*, order_id, tenant_id):
    """Exact-tenant read; never return another tenant's buyer digest."""
    if (type(order_id) is not str or not _ID.fullmatch(order_id)
            or type(tenant_id) is not str or not _ID.fullmatch(tenant_id)):
        raise DurableSignalOrderError("trusted_order_lookup_required")
    row = PendingSignalOrderRecord.objects.filter(
        order_id=order_id, tenant_id=tenant_id,
    ).first()
    return None if row is None else _check_row(row)
