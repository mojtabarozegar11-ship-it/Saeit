import pytest
from rest_framework.test import APIClient

from core.models import ApprovalRequest, KnowledgeArticle, Order, PaymentIntent, Product


@pytest.mark.django_db
def test_payment_intent_is_idempotent_and_requires_approval(django_user_model):
    owner = django_user_model.objects.create_user(
        username="payment-owner", password="x", is_staff=True
    )
    order = Order.objects.create(
        customer=owner, status="pending", total="250.00", currency="IRR"
    )
    client = APIClient()
    client.force_authenticate(user=owner)

    first = client.post(
        "/api/payments/create/",
        {"order_id": order.pk, "idempotency_key": "pay-order-1"},
        format="json",
    )
    assert first.status_code == 202
    intent = PaymentIntent.objects.get(order=order)
    assert str(intent.amount) == "250.00"
    assert intent.status == "awaiting_approval"
    approval = ApprovalRequest.objects.get(
        target_type="PaymentIntent", target_id=str(intent.pk)
    )
    assert approval.action_type == "payment"

    second = client.post(
        "/api/payments/create/",
        {"order_id": order.pk, "idempotency_key": "pay-order-1"},
        format="json",
    )
    assert second.status_code == 200
    assert second.data["payment_intent"]["id"] == intent.pk
    assert PaymentIntent.objects.filter(order=order).count() == 1


@pytest.mark.django_db
def test_payment_approval_moves_intent_to_gateway_ready(django_user_model):
    owner = django_user_model.objects.create_user(
        username="payment-approver", password="x", is_staff=True
    )
    order = Order.objects.create(
        customer=owner, status="pending", total="500.00", currency="IRR"
    )
    intent = PaymentIntent.objects.create(
        order=order,
        amount=order.total,
        currency=order.currency,
        idempotency_key="pay-order-2",
    )
    approval = ApprovalRequest.objects.create(
        action_type="payment",
        target_type="PaymentIntent",
        target_id=str(intent.pk),
        reason="Owner approval required",
        risk="critical",
        requested_by=owner,
    )
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True, "note": "Approved for gateway"},
        format="json",
    )
    assert response.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "ready_for_gateway"


@pytest.mark.django_db
def test_rejected_payment_does_not_become_gateway_ready(django_user_model):
    owner = django_user_model.objects.create_user(
        username="payment-reject", password="x", is_staff=True
    )
    order = Order.objects.create(
        customer=owner, status="pending", total="100.00", currency="IRR"
    )
    intent = PaymentIntent.objects.create(
        order=order,
        amount=order.total,
        currency=order.currency,
        idempotency_key="pay-order-3",
    )
    approval = ApprovalRequest.objects.create(
        action_type="payment",
        target_type="PaymentIntent",
        target_id=str(intent.pk),
        reason="Owner approval required",
        risk="critical",
        requested_by=owner,
    )
    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": False, "note": "Rejected"},
        format="json",
    )
    assert response.status_code == 200
    intent.refresh_from_db()
    assert intent.status == "rejected"
