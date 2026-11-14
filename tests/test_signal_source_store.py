"""Persistence and fraud-handling for signed market-signal event evidence."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac

from django.test import TestCase

from core.models import SignalSourceEvent
from core.signal_source_evidence import canonical_signal_bytes
from core.signal_source_store import (
    stage_signed_signal, SignalReceiptRejected,
)

NOW = datetime(2026, 11, 14, 19, 0, tzinfo=timezone.utc)
KEY = b"broker-adapter-private-only-unit-test-secret-value"
REGISTRY = {("saman", "sourceA"): KEY, ("zahra", "sourceA"): KEY}


class PersistedSignalEvidenceTests(TestCase):
    def setUp(self):
        self.record = {
            "event_id": "trader-20261114-001",
            "symbol": "XAUUSD", "side": "buy",
            "created_at": NOW - timedelta(minutes=5),
            "entry": "4000", "stop_loss": "3970",
            "take_profit": "4040", "verified_source": True,
        }

    def sign(self, record=None, brand="saman", source_id="sourceA"):
        data = canonical_signal_bytes(
            record=record if record is not None else self.record,
            brand=brand, source_id=source_id,
        )
        return hmac.new(KEY, data, sha256).hexdigest()

    def stage(self, **changes):
        brand = changes.get("brand", "saman")
        source_id = changes.get("source_id", "sourceA")
        record = changes.get("record", self.record)
        # A deliberately malformed source record cannot be signed as a
        # well-formed event; the caller may supply a precomputed valid
        # signature so that the *importer* rejection is under test.
        signature = changes.get("signature")
        if signature is None:
            signature = self.sign(record, brand, source_id)
        opts = {
            "brand": brand, "source_id": source_id, "record": record,
            "signature": signature,
            "trusted_source_keys": REGISTRY,
            "now": NOW,
        }
        opts.update(changes)
        return stage_signed_signal(**opts)

    def test_valid_origin_persists_one_pending_event(self):
        res = self.stage()
        self.assertEqual(res["result"], "recorded_pending_audit")
        self.assertTrue(res["source_authenticated"])
        self.assertFalse(res["performance_verified"])
        self.assertFalse(res["subscription_enabled"])
        self.assertFalse(res["delivered"])
        self.assertEqual(SignalSourceEvent.objects.count(), 1)
        event = SignalSourceEvent.objects.get()
        self.assertEqual(event.state, "pending_audit")
        self.assertEqual(event.brand, "saman")
        self.assertEqual(event.source_id, "sourceA")

    def test_identical_event_is_idempotent(self):
        self.stage()
        second = self.stage()
        self.assertEqual(second["result"], "already_recorded_pending")
        self.assertEqual(SignalSourceEvent.objects.count(), 1)

    def test_modified_event_with_same_id_is_conflict(self):
        self.stage()
        changed = {**self.record, "entry": "4001"}
        with self.assertRaisesMessage(SignalReceiptRejected, "conflicting_signal_event_replay"):
            self.stage(record=changed)
        self.assertEqual(SignalSourceEvent.objects.count(), 1)

    def test_cross_brand_does_not_read_other_brand_event(self):
        self.stage()
        self.stage(brand="zahra")
        self.assertEqual(SignalSourceEvent.objects.count(), 2)
        self.assertEqual(set(SignalSourceEvent.objects.values_list("brand", flat=True)), {"saman", "zahra"})

    def test_untrusted_source_cannot_save_event(self):
        with self.assertRaises(SignalReceiptRejected):
            self.stage(source_id="unlisted_source")
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_invalid_signature_prevents_db_write(self):
        with self.assertRaises(SignalReceiptRejected):
            self.stage(signature="0" * 64)
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_missing_registry_prevents_db_write(self):
        with self.assertRaises(SignalReceiptRejected):
            self.stage(trusted_source_keys={})
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_expired_timestamp_is_rejected(self):
        with self.assertRaises(SignalReceiptRejected):
            self.stage(now=NOW + timedelta(days=2))
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_future_timestamp_is_rejected(self):
        with self.assertRaises(SignalReceiptRejected):
            self.stage(now=NOW - timedelta(days=1))
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_incorrect_source_verified_boolean_rejected(self):
        modified = {**self.record, "verified_source": False}
        with self.assertRaises(SignalReceiptRejected):
            self.stage(record=modified, signature=self.sign())
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_fake_customer_payment_field_rejected(self):
        modified = {**self.record, "paid": True}
        with self.assertRaises(SignalReceiptRejected):
            self.stage(record=modified, signature=self.sign())
        self.assertFalse(SignalSourceEvent.objects.exists())

    def test_database_composite_uniqueness_enforced(self):
        self.stage()
        from django.db import IntegrityError, transaction
        existing = SignalSourceEvent.objects.get()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SignalSourceEvent.objects.create(
                    brand=existing.brand, source_id=existing.source_id,
                    event_id=existing.event_id, event_at=existing.event_at,
                    canonical_payload=existing.canonical_payload,
                    payload_sha256=existing.payload_sha256,
                    source_signature=existing.source_signature,
                )
        self.assertEqual(SignalSourceEvent.objects.count(), 1)

    def test_raw_received_payload_can_be_independently_rehashed(self):
        self.stage()
        receipt = SignalSourceEvent.objects.get()
        self.assertEqual(
            sha256(receipt.canonical_payload.encode("ascii")).hexdigest(),
            receipt.payload_sha256,
        )
        self.assertEqual(
            hmac.new(KEY, receipt.canonical_payload.encode("ascii"), sha256).hexdigest(),
            receipt.source_signature,
        )

    def test_tampered_already_recorded_digest_cannot_be_returned_as_success(self):
        self.stage()
        SignalSourceEvent.objects.update(payload_sha256="0" * 64)
        with self.assertRaises(SignalReceiptRejected):
            self.stage()

    def test_duplicate_event_never_creates_subscription_or_order(self):
        from core.models import Order, PaymentIntent
        self.stage()
        self.stage()
        self.assertFalse(Order.objects.exists())
        self.assertFalse(PaymentIntent.objects.exists())
