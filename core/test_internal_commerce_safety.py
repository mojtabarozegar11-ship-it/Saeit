"""Operational fixes for commerce transactions and owner-only payment approval."""
from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from .approval import ApprovalService
from .models import ApprovalRequest, KnowledgeArticle, LedgerEntry, Order, OrderItem, PaymentIntent, Product


User = get_user_model()


class InternalCommerceSafetyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="commerce-owner", email="commerce@example.org", password="safe-pass-123",
        )
        self.staff = User.objects.create_user(
            username="commerce-staff", password="safe-pass-123", is_staff=True,
        )
        self.article = KnowledgeArticle.objects.create(
            title="Research source", slug="commerce-source", content="Validated.", published=True,
        )
        self.product = Product.objects.create(
            title="Manual", product_type="digital", price=Decimal("15.00"),
            currency="IRR", active=True, owner=self.owner, knowledge_article=self.article,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_order_locks_product_inside_transaction(self):
        original = Product.objects.select_for_update

        def assert_transaction():
            self.assertTrue(connection.in_atomic_block)
            return original()

        with patch.object(Product.objects, "select_for_update", side_effect=assert_transaction):
            response = self.client.post(
                "/api/orders/", {"product_id": self.product.pk, "quantity": 2},
                format="json", secure=True,
            )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.get().quantity, 2)
        self.assertEqual(Order.objects.get().total, Decimal("30.00"))

    def test_payment_is_idempotent_and_only_creates_one_approval(self):
        order = Order.objects.create(customer=self.owner, total=Decimal("15.00"), currency="IRR")
        route = "/api/payments/create/"
        payload = {"order_id": order.pk, "idempotency_key": "one-key"}
        first = self.client.post(route, payload, format="json", secure=True)
        second = self.client.post(route, payload, format="json", secure=True)
        third = self.client.post(route, {**payload, "idempotency_key": "different"}, format="json", secure=True)
        self.assertEqual(first.status_code, 202, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(third.status_code, 409, third.data)
        self.assertEqual(PaymentIntent.objects.count(), 1)
        self.assertEqual(ApprovalRequest.objects.filter(target_type="PaymentIntent").count(), 1)

    def test_staff_cannot_create_or_approve_financial_obligation(self):
        order = Order.objects.create(customer=self.staff, total=Decimal("15.00"), currency="IRR")
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            "/api/payments/create/",
            {"order_id": order.pk, "idempotency_key": "staff-key"},
            format="json", secure=True,
        )
        self.assertEqual(response.status_code, 403)
        intent = PaymentIntent.objects.create(
            order=order, amount=Decimal("15.00"), currency="IRR", idempotency_key="legacy-staff"
        )
        approval = ApprovalRequest.objects.create(
            action_type="payment", target_type="PaymentIntent",
            target_id=str(intent.pk), reason="legacy request", risk="critical",
            requested_by=self.staff,
        )
        denied = self.client.post(
            f"/api/approvals/{approval.pk}/decide/",
            {"approved": True}, format="json", secure=True,
        )
        self.assertEqual(denied.status_code, 403)
        with self.assertRaises(ValueError):
            ApprovalService().decide(approval.pk, approved=True, actor_id=self.staff.pk)
        intent.refresh_from_db()
        self.assertEqual(intent.status, "awaiting_approval")

    def test_invalid_order_id_is_client_error(self):
        response = self.client.post(
            "/api/payments/create/",
            {"order_id": "not-an-id", "idempotency_key": "invalid"},
            format="json", secure=True,
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(PAYMENT_WEBHOOK_SECRET="integration-test-secret")
    def test_webhook_amount_format_and_late_failure_cannot_reverse_payment(self):
        order = Order.objects.create(customer=self.owner, total=Decimal("15.00"), currency="IRR")
        intent = PaymentIntent.objects.create(
            order=order, amount=Decimal("15.00"), currency="IRR",
            provider="pay-test", idempotency_key="webhook-key", status="gateway_pending",
        )

        def webhook(event_id, event_type, amount=None):
            payload = {
                "event_type": event_type,
                "payment_intent_id": intent.pk,
                "provider_reference": "processor-receipt-123",
            }
            if amount is not None:
                payload.update({"amount": amount, "currency": "IRR"})
            raw = json.dumps(payload, sort_keys=True).encode("utf-8")
            signature = hmac.new(b"integration-test-secret", raw, hashlib.sha256).hexdigest()
            return self.client.post(
                "/api/payment-webhooks/", raw, content_type="application/json",
                HTTP_X_PAYMENT_PROVIDER="pay-test", HTTP_X_PAYMENT_EVENT_ID=event_id,
                HTTP_X_PAYMENT_SIGNATURE=signature, secure=True,
            )

        success = webhook("evt-paid", "payment.succeeded", "15")
        self.assertEqual(success.status_code, 200, success.data)
        self.assertEqual(success.data["status"], "processed")
        late_failure = webhook("evt-late-fail", "payment.failed")
        self.assertEqual(late_failure.status_code, 200, late_failure.data)
        self.assertEqual(late_failure.data["status"], "ignored")
        intent.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(intent.status, "succeeded")
        self.assertEqual(order.status, "paid")
        self.assertEqual(LedgerEntry.objects.filter(order=order, entry_type="payment").count(), 1)

    @override_settings(PAYMENT_WEBHOOK_SECRET="integration-test-secret")
    def test_provider_receipt_cannot_settle_two_orders(self):
        orders = [
            Order.objects.create(customer=self.owner, total=Decimal("15.00"), currency="IRR")
            for _ in range(2)
        ]
        intents = [
            PaymentIntent.objects.create(
                order=order, amount=Decimal("15.00"), currency="IRR",
                provider="pay-test", idempotency_key=f"receipt-{index}",
                status="gateway_pending",
            )
            for index, order in enumerate(orders)
        ]

        def settle(intent, event_id):
            payload = {
                "event_type": "payment.succeeded",
                "payment_intent_id": intent.pk,
                "provider_reference": "same-provider-receipt",
                "amount": "15.00",
                "currency": "IRR",
            }
            raw = json.dumps(payload, sort_keys=True).encode("utf-8")
            signature = hmac.new(b"integration-test-secret", raw, hashlib.sha256).hexdigest()
            return self.client.post(
                "/api/payment-webhooks/", raw, content_type="application/json",
                HTTP_X_PAYMENT_PROVIDER="pay-test",
                HTTP_X_PAYMENT_EVENT_ID=event_id,
                HTTP_X_PAYMENT_SIGNATURE=signature, secure=True,
            )

        first = settle(intents[0], "evt-first")
        second = settle(intents[1], "evt-second")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 409, second.data)
        for order, intent in zip(orders, intents):
            order.refresh_from_db()
            intent.refresh_from_db()
        self.assertEqual(orders[0].status, "paid")
        self.assertEqual(intents[0].status, "succeeded")
        self.assertEqual(orders[1].status, "pending")
        self.assertEqual(intents[1].status, "gateway_pending")
        self.assertEqual(LedgerEntry.objects.filter(entry_type="payment").count(), 1)
