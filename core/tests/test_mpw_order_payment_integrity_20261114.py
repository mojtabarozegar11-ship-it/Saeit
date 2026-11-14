"""Source-only integration of bounded pending orders and authenticated webhook.

All HTTP requests target Django's isolated TestCase database. No payment
provider calls, customer emails, asset delivery or production writes.
"""
from decimal import Decimal
import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.commerce_integrity import ledger_reference
from core.models import (
    ApprovalRequest, KnowledgeArticle, LedgerEntry, Order,
    OrderItem, PaymentIntent, PaymentWebhookEvent, Product,
)

SECRET = "X" * 32
PROVIDER = "named-provider"


@override_settings(
    PAYMENT_WEBHOOK_SECRET=SECRET,
    PAYMENT_WEBHOOK_ALLOWED_PROVIDERS=(PROVIDER,),
)
class OrderPaymentSourceContractTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="commerce-intg-buyer", email="paying@farm-commerce.org",
            password="offline-tests-only", is_staff=True,
        )
        self.other = User.objects.create_user(
            username="commerce-intg-other", email="other@farm-commerce.org",
            password="offline-tests-only", is_staff=True,
        )
        self.article = KnowledgeArticle.objects.create(
            title="Published order evidence", slug="commerce-integrity-20261114",
            content="Synthetic reference only", published=True,
        )
        self.product = Product.objects.create(
            title="Farm analysis reference", product_type="digital",
            price=Decimal("125.50"), currency="USD", active=True,
            knowledge_article=self.article, owner=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def create_order(self, **overrides):
        data = {"product_id": self.product.pk, "quantity": 1}
        data.update(overrides)
        return self.client.post("/api/orders/", data, format="json")

    def make_order(self, *, status="pending", amount="125.50", currency="USD", user=None):
        order = Order.objects.create(
            customer=user or self.user, status=status,
            total=Decimal(amount), currency=currency,
        )
        OrderItem.objects.create(
            order=order, product=self.product, quantity=1,
            unit_price=Decimal(amount), currency=currency,
        )
        return order

    def ready_intent(self, *, amount="125.50", status="ready_for_gateway",
                     order=None, key="webhook-intent-01"):
        order = order or self.make_order()
        return PaymentIntent.objects.create(
            order=order, amount=Decimal(amount), currency=order.currency,
            idempotency_key=key, status=status, provider=PROVIDER,
        )

    def signed_event(self, intent, *, event="payment.succeeded", event_id="evt-0001",
                     body=None, provider=PROVIDER, secret=SECRET):
        if body is None:
            body = {
                "event_type": event,
                "payment_intent_id": intent.pk,
                "provider_reference": "actual-provider-reference-01",
            }
            if event == "payment.succeeded":
                body.update(amount="125.50", currency="USD")
        if isinstance(body, bytes):
            raw = body
        else:
            raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return APIClient().generic(
            "POST", "/api/payment-webhooks/", data=raw,
            content_type="application/json",
            HTTP_X_PAYMENT_PROVIDER=provider,
            HTTP_X_PAYMENT_EVENT_ID=event_id,
            HTTP_X_PAYMENT_SIGNATURE=sig,
        )

    def test_01_order_total_owned_by_server(self):
        response = self.create_order(quantity=3, total="0.01", status="paid", customer=999)
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["order"]["id"])
        self.assertEqual(order.total, Decimal("376.50"))
        self.assertEqual(order.status, "pending")
        self.assertEqual(order.customer_id, self.user.pk)

    def test_02_missing_product_id_rejected(self):
        self.assertEqual(
            self.client.post("/api/orders/", {"quantity": 1}, format="json").status_code, 400
        )
        self.assertFalse(Order.objects.exists())

    def test_03_product_id_boolean_rejected(self):
        self.assertEqual(self.create_order(product_id=True).status_code, 400)

    def test_04_product_id_array_rejected(self):
        self.assertEqual(self.create_order(product_id=[self.product.pk]).status_code, 400)

    def test_05_quantity_boolean_rejected(self):
        self.assertEqual(self.create_order(quantity=True).status_code, 400)

    def test_06_quantity_float_rejected(self):
        self.assertEqual(self.create_order(quantity=2.5).status_code, 400)

    def test_07_quantity_over_100_rejected(self):
        self.assertEqual(self.create_order(quantity=101).status_code, 400)

    def test_08_zero_quantity_rejected(self):
        self.assertEqual(self.create_order(quantity=0).status_code, 400)

    def test_09_canonical_quantity_string_accepted(self):
        self.assertEqual(self.create_order(quantity="2").status_code, 201)

    def test_10_inactive_product_rejected(self):
        self.product.active = False
        self.product.save(update_fields=["active"])
        self.assertEqual(self.create_order().status_code, 404)

    def test_11_unpublished_knowledge_product_rejected(self):
        self.article.published = False
        self.article.save(update_fields=["published"])
        self.assertEqual(self.create_order().status_code, 404)

    def test_12_zero_price_blocks_new_invoice(self):
        self.product.price = Decimal("0.00")
        self.product.save(update_fields=["price"])
        self.assertEqual(self.create_order().status_code, 409)

    def test_13_negative_price_blocks_new_invoice(self):
        self.product.price = Decimal("-1.00")
        self.product.save(update_fields=["price"])
        self.assertEqual(self.create_order().status_code, 409)

    def test_14_price_times_quantity_overflow_blocks(self):
        self.product.price = Decimal("999999999999.99")
        self.product.save(update_fields=["price"])
        self.assertEqual(self.create_order(quantity=2).status_code, 409)

    def test_15_invalid_currency_blocks_new_invoice(self):
        self.product.currency = "usd"
        self.product.save(update_fields=["currency"])
        self.assertEqual(self.create_order().status_code, 409)

    def test_16_order_failure_does_not_write_partial_item(self):
        self.product.price = Decimal("0")
        self.product.save(update_fields=["price"])
        self.assertEqual(self.create_order().status_code, 409)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_17_intent_can_be_created_once_with_approval(self):
        order = self.make_order()
        response = self.client.post(
            "/api/payments/create/",
            {"order_id": order.pk, "idempotency_key": "invoice-key-0001"},
            format="json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(PaymentIntent.objects.filter(order=order).count(), 1)
        self.assertEqual(ApprovalRequest.objects.filter(target_type="PaymentIntent").count(), 1)

    def test_18_repeat_intent_is_idempotent(self):
        order = self.make_order()
        data = {"order_id": order.pk, "idempotency_key": "invoice-key-0002"}
        self.assertEqual(self.client.post("/api/payments/create/", data, format="json").status_code, 202)
        self.assertEqual(self.client.post("/api/payments/create/", data, format="json").status_code, 200)
        self.assertEqual(PaymentIntent.objects.count(), 1)
        self.assertEqual(ApprovalRequest.objects.count(), 1)

    def test_19_changed_key_for_same_order_rejected(self):
        order = self.make_order()
        a = {"order_id": order.pk, "idempotency_key": "invoice-key-0003"}
        self.assertEqual(self.client.post("/api/payments/create/", a, format="json").status_code, 202)
        a["idempotency_key"] = "invoice-key-0004"
        self.assertEqual(self.client.post("/api/payments/create/", a, format="json").status_code, 409)

    def test_20_reusing_key_for_other_order_rejected(self):
        a, b = self.make_order(), self.make_order()
        first = {"order_id": a.pk, "idempotency_key": "invoice-key-0005"}
        other = {"order_id": b.pk, "idempotency_key": "invoice-key-0005"}
        self.assertEqual(self.client.post("/api/payments/create/", first, format="json").status_code, 202)
        self.assertEqual(self.client.post("/api/payments/create/", other, format="json").status_code, 409)

    def test_21_intent_boolean_id_rejected(self):
        self.assertEqual(self.client.post(
            "/api/payments/create/", {"order_id": True, "idempotency_key": "invoice-key-0006"},
            format="json").status_code, 400)

    def test_22_intent_malformed_key_rejected(self):
        order = self.make_order()
        self.assertEqual(self.client.post(
            "/api/payments/create/", {"order_id": order.pk, "idempotency_key": ["unsafe"]},
            format="json").status_code, 400)

    def test_23_intent_must_belong_to_current_user(self):
        other_order = self.make_order(user=self.other)
        self.assertEqual(self.client.post(
            "/api/payments/create/", {"order_id": other_order.pk, "idempotency_key": "invoice-key-0007"},
            format="json").status_code, 404)

    def test_24_intent_from_paid_order_rejected(self):
        paid = self.make_order(status="paid")
        self.assertEqual(self.client.post(
            "/api/payments/create/", {"order_id": paid.pk, "idempotency_key": "invoice-key-0008"},
            format="json").status_code, 409)

    def test_25_intent_from_zero_order_rejected(self):
        order = self.make_order(amount="0.00")
        self.assertEqual(self.client.post(
            "/api/payments/create/", {"order_id": order.pk, "idempotency_key": "invoice-key-0009"},
            format="json").status_code, 409)

    def test_26_webhook_matching_event_stores_hashed_ledger_once(self):
        intent = self.ready_intent()
        response = self.signed_event(intent)
        self.assertEqual(response.status_code, 200, response.content)
        ref = ledger_reference(PROVIDER, "evt-0001")
        self.assertEqual(LedgerEntry.objects.filter(reference=ref).count(), 1)
        intent.refresh_from_db()
        intent.order.refresh_from_db()
        self.assertEqual(intent.status, "succeeded")
        self.assertEqual(intent.order.status, "paid")

    def test_27_exact_duplicate_event_idempotent(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent).status_code, 200)
        self.assertEqual(self.signed_event(intent).status_code, 200)
        self.assertEqual(PaymentWebhookEvent.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_28_conflicting_duplicate_event_rejected(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent).status_code, 200)
        altered = {"event_type": "payment.failed", "payment_intent_id": intent.pk,
                   "provider_reference": "actual-provider-reference-01"}
        self.assertEqual(self.signed_event(intent, body=altered).status_code, 409)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_29_late_failure_cannot_downgrade_paid_order(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent).status_code, 200)
        r = self.signed_event(intent, event="payment.failed", event_id="evt-late-0002")
        self.assertEqual(r.status_code, 409)
        intent.refresh_from_db()
        self.assertEqual(intent.status, "succeeded")

    def test_30_unsigned_event_rejected(self):
        intent = self.ready_intent()
        response = self.signed_event(intent, secret="WRONG"*7)
        self.assertEqual(response.status_code, 401)
        self.assertFalse(PaymentWebhookEvent.objects.exists())

    def test_31_provider_without_allowlist_rejected(self):
        intent = self.ready_intent()
        with override_settings(PAYMENT_WEBHOOK_ALLOWED_PROVIDERS=()):
            self.assertEqual(self.signed_event(intent).status_code, 401)

    def test_32_demo_provider_never_authorizes_money(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent, provider="demo").status_code, 401)

    def test_33_missing_reference_rejected(self):
        intent = self.ready_intent()
        payload = {"event_type": "payment.succeeded", "payment_intent_id": intent.pk,
                   "amount": "125.50", "currency": "USD"}
        self.assertEqual(self.signed_event(intent, body=payload).status_code, 400)
        self.assertFalse(Order.objects.filter(status="paid").exists())

    def test_34_amount_float_rejected(self):
        intent = self.ready_intent()
        payload = {"event_type": "payment.succeeded", "payment_intent_id": intent.pk,
                   "provider_reference": "actual-provider-reference-01",
                   "amount": 125.50, "currency": "USD"}
        self.assertEqual(self.signed_event(intent, body=payload).status_code, 400)

    def test_35_amount_mismatch_rejected(self):
        intent = self.ready_intent()
        payload = {"event_type": "payment.succeeded", "payment_intent_id": intent.pk,
                   "provider_reference": "actual-provider-reference-01",
                   "amount": "125.49", "currency": "USD"}
        self.assertEqual(self.signed_event(intent, body=payload).status_code, 409)
        self.assertEqual(LedgerEntry.objects.count(), 0)

    def test_36_currency_mismatch_rejected(self):
        intent = self.ready_intent()
        payload = {"event_type": "payment.succeeded", "payment_intent_id": intent.pk,
                   "provider_reference": "actual-provider-reference-01",
                   "amount": "125.50", "currency": "IRR"}
        self.assertEqual(self.signed_event(intent, body=payload).status_code, 409)

    def test_37_duplicate_json_keys_rejected(self):
        intent = self.ready_intent()
        raw = (b'{"event_type":"payment.succeeded","event_type":"payment.failed",'
               + b'"payment_intent_id":' + str(intent.pk).encode()
               + b',"provider_reference":"actual-provider-reference-01"}')
        self.assertEqual(self.signed_event(intent, body=raw).status_code, 400)

    def test_38_json_array_rejected(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent, body=b"[]").status_code, 400)

    def test_39_missing_provider_configured_secret_denied(self):
        intent = self.ready_intent()
        with override_settings(PAYMENT_WEBHOOK_SECRET="short"):
            self.assertEqual(self.signed_event(intent).status_code, 401)

    def test_40_payment_failure_without_paid_order_is_processed(self):
        intent = self.ready_intent()
        r = self.signed_event(intent, event="payment.failed")
        self.assertEqual(r.status_code, 200, r.content)
        intent.refresh_from_db()
        self.assertEqual(intent.status, "failed")
        self.assertFalse(Order.objects.filter(status="paid").exists())

    def test_41_failure_after_paid_does_not_remove_original_ledger(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent).status_code, 200)
        self.signed_event(intent, event="payment.failed", event_id="evt-other-002")
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_42_provider_reference_reuse_denied(self):
        old = self.ready_intent(key="webhook-intent-02")
        self.assertEqual(self.signed_event(old, event_id="evt-old-02").status_code, 200)
        newer = self.ready_intent(key="webhook-intent-03")
        response = self.signed_event(newer, event_id="evt-new-03")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_43_wrong_provider_intent_cannot_settle(self):
        intent = self.ready_intent()
        intent.provider = "different-provider"
        intent.save(update_fields=["provider"])
        self.assertEqual(self.signed_event(intent).status_code, 404)

    def test_44_source_amount_state_conflict_denied(self):
        intent = self.ready_intent(amount="125.49")
        self.assertEqual(self.signed_event(intent).status_code, 409)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_45_payment_does_not_emit_real_delivery(self):
        intent = self.ready_intent()
        self.assertEqual(self.signed_event(intent).status_code, 200)
        from core.models import CommerceFunnelEvent
        self.assertEqual(CommerceFunnelEvent.objects.filter(event_name="delivery_success").count(), 0)
        self.assertEqual(Order.objects.filter(status="paid").count(), 1)
