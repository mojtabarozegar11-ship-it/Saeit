import pytest
from rest_framework.test import APIClient

from core.models import KnowledgeArticle, Order, Product


@pytest.mark.django_db(transaction=True)
def test_order_product_lock_is_inside_transaction(django_user_model, monkeypatch):
    from django.db import connection
    user = django_user_model.objects.create_user(username='lock-owner', is_staff=True)
    article = KnowledgeArticle.objects.create(title='Approved', slug='lock-approved',
                                             content='content', published=True)
    product = Product.objects.create(title='Service', product_type='service', price='49',
                                     currency='TRX', active=True, knowledge_article=article)
    original = Product.objects.select_for_update
    calls = []
    def require_transaction(*args, **kwargs):
        assert connection.in_atomic_block
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(Product.objects, 'select_for_update', require_transaction)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/orders/', {'product_id':product.pk}, format='json')
    assert response.status_code == 201
    assert calls == [True]


@pytest.mark.django_db
def test_order_uses_active_product_price_and_server_total(django_user_model):
    user = django_user_model.objects.create_user(
        username="order-owner", password="x", is_staff=True
    )
    article = KnowledgeArticle.objects.create(
        title="Published knowledge",
        slug="order-published-knowledge",
        content="content",
        published=True,
    )
    product = Product.objects.create(
        title="Approved service",
        product_type="service",
        price="125.50",
        currency="IRR",
        active=True,
        owner=user,
        knowledge_article=article,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/orders/",
        {
            "product_id": product.pk,
            "quantity": 3,
            "total": "1",
            "status": "paid",
            "customer": 999999,
        },
        format="json",
    )

    assert response.status_code == 201
    order = Order.objects.get(pk=response.data["order"]["id"])
    assert order.customer_id == user.pk
    assert order.status == "pending"
    assert str(order.total) == "376.50"
    item = order.items.get()
    assert item.quantity == 3
    assert str(item.unit_price) == "125.50"
    assert item.currency == "IRR"


@pytest.mark.django_db
def test_order_rejects_inactive_product(django_user_model):
    user = django_user_model.objects.create_user(
        username="order-owner-inactive", password="x", is_staff=True
    )
    article = KnowledgeArticle.objects.create(
        title="Published knowledge inactive",
        slug="order-inactive-knowledge",
        content="content",
        published=True,
    )
    product = Product.objects.create(
        title="Inactive service",
        product_type="service",
        price="100",
        active=False,
        owner=user,
        knowledge_article=article,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/orders/", {"product_id": product.pk, "quantity": 1}, format="json"
    )

    assert response.status_code == 404
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_order_rejects_nonpositive_quantity(django_user_model):
    user = django_user_model.objects.create_user(
        username="order-owner-quantity", password="x", is_staff=True
    )
    article = KnowledgeArticle.objects.create(
        title="Published quantity knowledge",
        slug="order-quantity-knowledge",
        content="content",
        published=True,
    )
    product = Product.objects.create(
        title="Quantity service",
        product_type="service",
        price="100",
        active=True,
        owner=user,
        knowledge_article=article,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/orders/", {"product_id": product.pk, "quantity": 0}, format="json"
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0
