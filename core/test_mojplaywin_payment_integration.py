"""Payment-intent integration tests; no external gateway is called."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from core.api import PaymentIntentViewSet
from core.models import ApprovalRequest, Order, PaymentIntent


class PaymentIntentIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mpw_payment_staff", password="test-only-password", is_staff=True
        )
        self.other = get_user_model().objects.create_user(
            username="mpw_payment_other", password="test-only-password", is_staff=True
        )
        self.order = Order.objects.create(
            customer=self.user, total=Decimal("25.00"), currency="USD", status="pending"
        )
        self.factory = APIRequestFactory()
        self.view = PaymentIntentViewSet.as_view({"post": "create_intent"})

    def request(self, user, order_id, key):
        request = self.factory.post(
            "/api/payments/create/",
            {"order_id": order_id, "idempotency_key": key},
            format="json",
        )
        force_authenticate(request, user=user)
        return self.view(request)

    def test_creates_pending_intent_with_owner_approval(self):
        response = self.request(self.user, self.order.pk, "mpw-payment-key-1")
        self.assertEqual(response.status_code, 202)
        intent = PaymentIntent.objects.get()
        self.assertEqual(intent.amount, Decimal("25.00"))
        self.assertEqual(intent.provider, "not_configured")
        self.assertEqual(intent.status, "awaiting_approval")
        approval = ApprovalRequest.objects.get(target_type="PaymentIntent", target_id=str(intent.pk))
        self.assertEqual(approval.status, "pending")
        self.assertEqual(approval.action_type, "payment")

    def test_same_key_is_idempotent(self):
        self.assertEqual(self.request(self.user, self.order.pk, "mpw-payment-key-2").status_code, 202)
        self.assertEqual(self.request(self.user, self.order.pk, "mpw-payment-key-2").status_code, 200)
        self.assertEqual(PaymentIntent.objects.count(), 1)
        self.assertEqual(ApprovalRequest.objects.filter(action_type="payment").count(), 1)

    def test_other_customer_cannot_start_payment(self):
        response = self.request(self.other, self.order.pk, "mpw-payment-key-3")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PaymentIntent.objects.exists())

    def test_non_pending_order_cannot_start_payment(self):
        self.order.status = "paid"
        self.order.save()
        response = self.request(self.user, self.order.pk, "mpw-payment-key-4")
        self.assertEqual(response.status_code, 409)
        self.assertFalse(PaymentIntent.objects.exists())

    def test_oversized_idempotency_key_is_rejected(self):
        response = self.request(self.user, self.order.pk, 'x' * 129)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentIntent.objects.exists())
        self.assertFalse(ApprovalRequest.objects.filter(action_type='payment').exists())
