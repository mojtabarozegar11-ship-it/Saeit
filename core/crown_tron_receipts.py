"""Read-only Crown entitlement bridge for the isolated walletless TRX pilot.

This module does not observe a blockchain, write a payment, or trust a buyer
supplied transaction id. It accepts only the exact persisted receipt format
written *after* the independent solidified-node verifier has succeeded.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .models import LedgerEntry, PaymentWebhookEvent

PROVIDER = "mpw_walletless_trx_v1"
NETWORK = "tron-mainnet"
TX_HASH = re.compile(r"[0-9a-f]{64}\Z")
TRON_ADDRESS = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}\Z")


def verified_walletless_credit(order, intent):
    """Accept a single, reconciled, non-refunded server-settled receipt only.

    Receipt creation and independent chain verification belong to the payment
    adapter. This is a *consumer* of that adapter's durable MariaDB evidence,
    not a replacement for independent on-chain proof.
    """
    if (intent.provider != PROVIDER or intent.status != "paid"
            or order.status != "paid" or intent.order_id != order.pk
            or order.currency != "USD" or intent.currency != "USD"
            or intent.amount != order.total or order.total <= 0):
        return False
    try:
        doc = json.loads(intent.provider_reference)
        if (type(doc) is not dict
                or set(doc) != {"v", "to", "sun", "rate", "at"}
                or type(doc["v"]) is not int or doc["v"] != 1
                or not isinstance(doc["to"], str)
                or not TRON_ADDRESS.fullmatch(doc["to"])
                or type(doc["sun"]) is not int or not 0 < doc["sun"] < 10**18):
            return False
        rate = Decimal(str(doc["rate"]))
        when = datetime.fromisoformat(doc["at"])
        if (not rate.is_finite() or rate <= 0 or when.tzinfo is None
                or when.utcoffset() is None):
            return False
        expected_key = "wltrx1:" + hashlib.sha256(doc["to"].encode("ascii")).hexdigest() + ":" + str(doc["sun"])
        if intent.idempotency_key != expected_key:
            return False
    except (TypeError, ValueError, KeyError, InvalidOperation, OverflowError, AttributeError):
        return False

    events = list(PaymentWebhookEvent.objects.filter(
        payment_intent=intent, provider=PROVIDER,
        event_type="tron_finalized", status="processed",
    )[:2])
    if len(events) != 1:
        return False
    event = events[0]
    if (not TX_HASH.fullmatch(event.event_id or "")
            or not TX_HASH.fullmatch(event.payload_hash or "")):
        return False

    credits = list(LedgerEntry.objects.filter(
        order=order, payment_intent=intent, entry_type="credit",
    )[:2])
    if len(credits) != 1:
        return False
    credit = credits[0]
    metadata = credit.metadata if isinstance(credit.metadata, dict) else {}
    return bool(
        credit.amount == order.total
        and credit.currency == "USD"
        and credit.reference == "walletless:" + NETWORK + ":" + event.event_id
        and metadata.get("payment_method") == PROVIDER
        and metadata.get("network") == NETWORK
        and metadata.get("tx_hash") == event.event_id
        and metadata.get("evidence_digest") == event.payload_hash
        and type(metadata.get("walletless_receipt_event_id")) is int
        and metadata["walletless_receipt_event_id"] == event.pk
        and isinstance(metadata.get("sender"), str)
        and bool(metadata["sender"])
    )
