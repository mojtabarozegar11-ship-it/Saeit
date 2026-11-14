"""Django revenue evidence tests: server-record checks are NOT cash settlement."""
import json
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.economic_master_agent import EconomicMasterAgent
from core.models import (
    LedgerEntry, Order, OrderItem, PaymentIntent, PaymentWebhookEvent, Product,
)
from core.revenue_evidence_gate import (
    inspect_revenue_order, revenue_evidence_snapshot,
)


class RevenueEvidenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(
            username="evidence-buyer", email="buyer@example.invalid",
            password="offline-only",
        )
        self.owner = User.objects.create_superuser(
            username="evidence-owner", email="owner@example.invalid",
            password="offline-only",
        )
        self.staff = User.objects.create_user(
            username="evidence-staff", password="offline-only", is_staff=True,
        )
        self.product = Product.objects.create(
            title="Agricultural consulting document",
            product_type="digital", price="30.00", currency="USD",
            active=True, owner=self.owner,
        )
        self.order = Order.objects.create(
            customer=self.buyer, status="paid",
            total=Decimal("30.00"), currency="USD",
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product,
            quantity=1, unit_price="30.00", currency="USD",
        )
        self.intent = PaymentIntent.objects.create(
            order=self.order, amount="30.00", currency="USD",
            status="succeeded", idempotency_key="evidence-123456789",
            provider="named-provider", provider_reference="external-callback-id-1",
        )
        self.event = PaymentWebhookEvent.objects.create(
            payment_intent=self.intent, provider="named-provider",
            event_id="event-1", event_type="payment.succeeded",
            status="processed", payload_hash="a" * 64,
            processed_at=timezone.now(),
        )
        self.ledger = LedgerEntry.objects.create(
            order=self.order, payment_intent=self.intent,
            entry_type="payment", amount="30.00", currency="USD",
            reference="payment:" + "b" * 64,
            metadata={"provider": "named-provider", "event_id": "event-1"},
        )

    def check(self, code):
        self.assertIn(code, inspect_revenue_order(self.order)["reasons"])

    def test_01_consistent_records_unverified(self):
        record = inspect_revenue_order(self.order)
        self.assertEqual(record["state"], "internally_consistent_unverified")
        self.assertEqual(record["reasons"], [])

    def test_02_no_provider_confirmed_cash_value(self):
        record = inspect_revenue_order(self.order)
        self.assertIsNone(record["externally_settled_cash"])
        self.assertFalse(record["settlement_verified"])

    def test_03_pending_order_never_counts_as_paid(self):
        self.order.status = "pending"
        self.order.save(update_fields=["status"])
        self.assertEqual(inspect_revenue_order(self.order)["state"], "not_paid")

    def test_04_zero_order_amount(self):
        self.order.total = Decimal("0")
        self.order.save(update_fields=["total"])
        self.check("ORDER_AMOUNT_INVALID")

    def test_05_negative_order_amount(self):
        self.order.total = Decimal("-1")
        self.order.save(update_fields=["total"])
        self.check("ORDER_AMOUNT_INVALID")

    def test_06_bad_currency(self):
        self.order.currency = "usd!"
        self.order.save(update_fields=["currency"])
        self.check("ORDER_CURRENCY_INVALID")

    def test_07_missing_item(self):
        self.item.delete()
        self.check("ORDER_ITEMS_MISSING")

    def test_08_invalid_quantity(self):
        self.item.quantity = 0
        self.item.save(update_fields=["quantity"])
        self.check("ORDER_ITEM_QUANTITY_INVALID")

    def test_09_invalid_item_price(self):
        self.item.unit_price = Decimal("0")
        self.item.save(update_fields=["unit_price"])
        self.check("ORDER_ITEM_PRICE_INVALID")

    def test_10_mismatched_item_currency(self):
        self.item.currency = "IRR"
        self.item.save(update_fields=["currency"])
        self.check("ORDER_ITEM_CURRENCY_MISMATCH")

    def test_11_line_total_mismatch(self):
        self.item.unit_price = Decimal("25")
        self.item.save(update_fields=["unit_price"])
        self.check("ORDER_LINE_SUM_MISMATCH")

    def test_12_missing_payment_intent(self):
        order = Order.objects.create(
            customer=self.buyer, status="paid", total="30.00", currency="USD",
        )
        OrderItem.objects.create(order=order, product=self.product,
            quantity=1, unit_price="30.00", currency="USD")
        self.assertIn("PAYMENT_INTENT_MISSING", inspect_revenue_order(order)["reasons"])

    def test_13_intent_amount_mismatch(self):
        self.intent.amount = Decimal("29.99")
        self.intent.save(update_fields=["amount"])
        self.check("PAYMENT_AMOUNT_MISMATCH")

    def test_14_intent_currency_mismatch(self):
        self.intent.currency = "IRR"
        self.intent.save(update_fields=["currency"])
        self.check("PAYMENT_CURRENCY_MISMATCH")

    def test_15_demo_provider_not_cash_proof(self):
        self.intent.provider = "demo"
        self.intent.save(update_fields=["provider"])
        self.check("PROVIDER_NOT_INDEPENDENTLY_CONFIGURED")

    def test_16_provider_not_configured(self):
        self.intent.provider = "not_configured"
        self.intent.save(update_fields=["provider"])
        self.check("PROVIDER_NOT_INDEPENDENTLY_CONFIGURED")

    def test_17_too_short_idempotency(self):
        self.intent.idempotency_key = "bad"
        self.intent.save(update_fields=["idempotency_key"])
        self.check("PAYMENT_IDEMPOTENCY_INVALID")

    def test_18_empty_provider_reference(self):
        self.intent.provider_reference = ""
        self.intent.save(update_fields=["provider_reference"])
        self.check("PROVIDER_REFERENCE_MISSING")

    def test_19_reused_provider_reference(self):
        other = Order.objects.create(
            customer=self.buyer, status="pending", total="30.00", currency="USD",
        )
        PaymentIntent.objects.create(
            order=other, amount="30.00", currency="USD",
            provider="named-provider", provider_reference="external-callback-id-1",
            idempotency_key="another-unique-key-9",
        )
        self.check("PROVIDER_REFERENCE_REUSED")

    def test_20_refund_blocks_consistency(self):
        LedgerEntry.objects.create(
            order=self.order, entry_type="refund", amount="30",
            currency="USD", reference="refund:proof-1",
        )
        self.check("PAYMENT_REVERSAL_PRESENT")

    def test_21_chargeback_blocks_consistency(self):
        LedgerEntry.objects.create(
            order=self.order, entry_type="chargeback", amount="30",
            currency="USD", reference="cb:proof-1",
        )
        self.check("PAYMENT_REVERSAL_PRESENT")

    def test_22_intent_not_succeeded(self):
        self.intent.status = "ready_for_gateway"
        self.intent.save(update_fields=["status"])
        self.check("PAYMENT_INTENT_NOT_SUCCEEDED")

    def test_23_payment_ledger_missing(self):
        self.ledger.delete()
        self.check("PAYMENT_LEDGER_NOT_UNIQUE")

    def test_24_payment_ledger_duplicate(self):
        LedgerEntry.objects.create(
            order=self.order, payment_intent=self.intent,
            entry_type="payment", amount="30.00", currency="USD",
            reference="payment:" + "c" * 64,
        )
        self.check("PAYMENT_LEDGER_NOT_UNIQUE")

    def test_25_payment_ledger_underpaid(self):
        self.ledger.amount = Decimal("29")
        self.ledger.save(update_fields=["amount"])
        self.check("PAYMENT_LEDGER_MISMATCH")

    def test_26_payment_ledger_wrong_currency(self):
        self.ledger.currency = "IRR"
        self.ledger.save(update_fields=["currency"])
        self.check("PAYMENT_LEDGER_MISMATCH")

    def test_27_untrusted_ledger_reference(self):
        self.ledger.reference = "unverified:fake"
        self.ledger.save(update_fields=["reference"])
        self.check("PAYMENT_LEDGER_MISMATCH")

    def test_28_webhook_missing(self):
        self.event.delete()
        self.check("WEBHOOK_EVENT_NOT_UNIQUE")

    def test_29_webhook_duplicate(self):
        PaymentWebhookEvent.objects.create(
            payment_intent=self.intent, provider="named-provider",
            event_id="event-2", event_type="payment.succeeded",
            status="processed", payload_hash="b"*64, processed_at=timezone.now(),
        )
        self.check("WEBHOOK_EVENT_NOT_UNIQUE")

    def test_30_webhook_unprocessed(self):
        self.event.status = "received"
        self.event.save(update_fields=["status"])
        self.check("WEBHOOK_EVENT_NOT_UNIQUE")

    def test_31_invalid_webhook_payload_hash(self):
        self.event.payload_hash = "invalid"
        self.event.save(update_fields=["payload_hash"])
        self.check("WEBHOOK_EVIDENCE_INCOMPLETE")

    def test_32_webhook_missing_processed_time(self):
        self.event.processed_at = None
        self.event.save(update_fields=["processed_at"])
        self.check("WEBHOOK_EVIDENCE_INCOMPLETE")

    def test_33_webhook_ledger_binding_mismatch(self):
        self.ledger.metadata = {"provider": "named-provider", "event_id": "fake"}
        self.ledger.save(update_fields=["metadata"])
        self.check("WEBHOOK_LEDGER_BINDING_MISMATCH")

    def test_34_suspicious_walletless_does_not_pass_generic_guard(self):
        self.intent.provider = "mpw_walletless_trx_v1"
        self.intent.status = "paid"
        self.intent.save(update_fields=["provider", "status"])
        self.check("TRON_INTERNAL_RECEIPT_INCONSISTENT")

    def test_35_nominal_snapshot_not_income(self):
        data = revenue_evidence_snapshot()
        self.assertEqual(data["sampled_order_count"], 1)
        self.assertEqual(data["internally_consistent_nominal_not_cash"], {"USD": "30.00"})
        self.assertIsNone(data["externally_settled_cash"])
        self.assertFalse(data["revenue_claim_allowed"])

    def test_36_snapshot_is_read_only(self):
        before = (
            Order.objects.count(), LedgerEntry.objects.count(),
            PaymentWebhookEvent.objects.count(), PaymentIntent.objects.count(),
        )
        revenue_evidence_snapshot()
        self.assertEqual(before, (
            Order.objects.count(), LedgerEntry.objects.count(),
            PaymentWebhookEvent.objects.count(), PaymentIntent.objects.count(),
        ))

    def test_37_sample_is_not_extrapolated(self):
        data = revenue_evidence_snapshot(max_orders=1)
        self.assertTrue(data["sample_complete"])
        Order.objects.create(customer=self.buyer, status="pending",
                             total="10.00", currency="USD")
        data = revenue_evidence_snapshot(max_orders=1)
        self.assertEqual(data["sampled_order_count"], 1)
        self.assertFalse(data["sample_complete"])

    def test_38_invalid_window_denied(self):
        with self.assertRaises(ValueError):
            revenue_evidence_snapshot(days=0)

    def test_39_boolean_limit_denied(self):
        with self.assertRaises(ValueError):
            revenue_evidence_snapshot(max_orders=True)

    def test_40_anonymous_endpoint_denied(self):
        response = self.client.get(
            "/staff/command-center/api/bot/revenue-evidence/"
        )
        self.assertEqual(response.status_code, 403)

    def test_41_staff_endpoint_denied(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            "/staff/command-center/api/bot/revenue-evidence/"
        )
        self.assertEqual(response.status_code, 403)

    def test_42_owner_endpoint_has_no_buyer_pii(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            "/staff/command-center/api/bot/revenue-evidence/"
        )
        self.assertEqual(response.status_code, 200)
        raw = response.content.decode("utf-8")
        self.assertNotIn("buyer@example.invalid", raw)
        self.assertNotIn("external-callback-id", raw)
        self.assertEqual(response.json()["bot_id"], "mojtaba.bot.ai")
        self.assertIn("no-store", response["Cache-Control"])

    def test_43_post_endpoint_forbidden(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/staff/command-center/api/bot/revenue-evidence/", {}
        )
        self.assertEqual(response.status_code, 405)

    def test_44_readonly_cli_emits_no_cash_assumption(self):
        stream = StringIO()
        call_command("mojtaba_revenue_evidence_readonly", stdout=stream)
        data = json.loads(stream.getvalue())
        self.assertIsNone(data["externally_settled_cash"])
        self.assertFalse(data["settlement_provider_independently_checked"])

    def test_45_single_bot_method_returns_same_snapshot(self):
        data = EconomicMasterAgent().inspect_revenue_evidence_readonly()
        self.assertEqual(data["bot_id"], "mojtaba.bot.ai")
        self.assertEqual(data["sampled_order_count"], 1)

    def test_46_reasons_do_not_expose_customer_identity(self):
        record = inspect_revenue_order(self.order)
        self.assertNotIn("buyer@example.invalid", str(record))
        self.assertNotIn("external-callback-id", str(record))

    def test_47_bad_record_is_safe(self):
        result = inspect_revenue_order(None)
        self.assertEqual(result["state"], "invalid_record")
        self.assertIsNone(result["externally_settled_cash"])

    def test_48_no_delivery_claim(self):
        data = revenue_evidence_snapshot()
        self.assertFalse(data["live_delivery_verified"])
        self.assertIsNone(data["verified_net_profit"])

    def test_49_operator_permission_deactivated(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.client.force_login(self.owner)
        response = self.client.get(
            "/staff/command-center/api/bot/revenue-evidence/"
        )
        self.assertIn(response.status_code, (302, 403))

    def test_50_all_consistent_evidence_is_not_external_settlement(self):
        for _ in range(2):
            record = inspect_revenue_order(self.order)
            self.assertEqual(record["state"], "internally_consistent_unverified")
            self.assertIs(record["settlement_verified"], False)
