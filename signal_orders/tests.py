"""Django DB tests: pending signal orders survive independent service calls."""
import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from django.test import TestCase

from core.mojtaba_signal_order_contract import SignalOrderIntent, SignalOrderContractError
from core.mojtaba_signal_service_contract import (
    BOT_IDENTITY, SignalOffer, SignalServiceKind, SignalTenantRoute,
)
from .models import PendingSignalOrderRecord
from .service import DurableSignalOrderError, persist_pending_order, read_pending_order


NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


class DurablePendingOrderTests(TestCase):
    def setUp(self):
        self.route = SignalTenantRoute(
            tenant_id="mojplaywin", canonical_host="mojplaywin.com",
            path_prefix="/signals/", language="en",
            owner_approved=True, legal_reviewed=True, active=True,
        )
        self.offer = SignalOffer(
            offer_id="economic-report", tenant_id="mojplaywin",
            bot_identity=BOT_IDENTITY, language="en",
            service_kind=SignalServiceKind.ECONOMIC_REPORT,
            price=Decimal("11.5"), currency="TRX",
            owner_approved=True, legal_reviewed=True,
            rights_cleared=True, active=True,
        )
        self.intent = SignalOrderIntent(
            order_id="order-0001", tenant_id="mojplaywin",
            offer_id="economic-report", bot_identity=BOT_IDENTITY,
            language="en", price=Decimal("11.5"), currency="TRX",
            customer_ref_digest=hashlib.sha256(b"buyer-reference").hexdigest(),
            requested_at="2026-11-15T11:59:00Z",
        )

    def write(self, intent=None, route=None, offer=None):
        return persist_pending_order(
            intent if intent is not None else self.intent,
            route if route is not None else self.route,
            offer if offer is not None else self.offer,
            now=NOW,
        )

    def test_order_is_durable_pending_row_not_payment(self):
        written = self.write()
        self.assertTrue(written.created)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)
        self.assertEqual(written.record["state"], "awaiting_external_settlement")
        self.assertIs(written.record["settlement_verified"], False)
        self.assertIs(written.record["entitlement_granted"], False)

    def test_repeat_order_idempotent_across_database_queries(self):
        self.write()
        replay = self.write()
        self.assertFalse(replay.created)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)

    def test_different_customer_cannot_reuse_existing_id(self):
        self.write()
        from dataclasses import replace
        altered = replace(self.intent, customer_ref_digest=hashlib.sha256(b"different").hexdigest())
        with self.assertRaisesRegex(DurableSignalOrderError, "order_id_conflict"):
            self.write(intent=altered)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 1)

    def test_same_id_cannot_be_reused_across_tenants(self):
        self.write()
        from dataclasses import replace
        other_intent = replace(self.intent, tenant_id="other")
        other_route = replace(self.route, tenant_id="other", canonical_host="other.example")
        other_offer = replace(self.offer, tenant_id="other")
        with self.assertRaisesRegex(DurableSignalOrderError, "order_id_conflict"):
            self.write(other_intent, other_route, other_offer)

    def test_reader_restricts_tenant_scope(self):
        self.write()
        self.assertIsNone(read_pending_order(order_id="order-0001", tenant_id="another"))
        self.assertEqual(
            read_pending_order(order_id="order-0001", tenant_id="mojplaywin")["offer_id"],
            "economic-report",
        )

    def test_reader_rejects_invalid_untrusted_ids(self):
        for bad in (None, "", "x", "../private", "X" * 500):
            with self.subTest(bad=str(bad)[:20]), self.assertRaisesRegex(
                DurableSignalOrderError, "trusted_order_lookup_required"
            ):
                read_pending_order(order_id=bad, tenant_id="mojplaywin")

    def test_reader_detects_modified_payment_flags(self):
        self.write()
        row = PendingSignalOrderRecord.objects.get(order_id="order-0001")
        row.payload["entitlement_granted"] = True
        row.save(update_fields=["payload"])
        with self.assertRaisesRegex(DurableSignalOrderError, "stored_order_integrity_invalid"):
            read_pending_order(order_id="order-0001", tenant_id="mojplaywin")

    def test_reader_detects_mutated_price_even_without_flag_changes(self):
        self.write()
        row = PendingSignalOrderRecord.objects.get(order_id="order-0001")
        row.payload["price"] = "1"
        row.save(update_fields=["payload"])
        with self.assertRaisesRegex(DurableSignalOrderError, "stored_order_integrity_invalid"):
            read_pending_order(order_id="order-0001", tenant_id="mojplaywin")

    def test_reader_detects_order_owner_mismatch(self):
        self.write()
        row = PendingSignalOrderRecord.objects.get(order_id="order-0001")
        row.payload["tenant_id"] = "another"
        row.save(update_fields=["payload"])
        with self.assertRaisesRegex(DurableSignalOrderError, "stored_order_integrity_invalid"):
            read_pending_order(order_id="order-0001", tenant_id="mojplaywin")

    def test_invalid_active_offer_does_not_write_any_row(self):
        from dataclasses import replace
        bad_offer = replace(self.offer, active=False)
        with self.assertRaises(SignalOrderContractError):
            self.write(offer=bad_offer)
        self.assertEqual(PendingSignalOrderRecord.objects.count(), 0)

    def test_pending_record_not_raw_email_or_password(self):
        receipt = self.write()
        self.assertNotIn("buyer-reference", str(receipt.record))
        self.assertNotIn("password", str(receipt.record))
        self.assertNotIn("email@", str(receipt.record))

    def test_receipt_mutation_cannot_change_durable_row(self):
        receipt = self.write()
        receipt.record["entitlement_granted"] = True
        self.assertFalse(
            read_pending_order(order_id="order-0001", tenant_id="mojplaywin")[
                "entitlement_granted"
            ]
        )
