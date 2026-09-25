import pytest
from rest_framework.test import APIClient

from core.models import ApprovalRequest, KnowledgeArticle, Product, ResearchProject
from core.research_runtime import ResearchRuntime


@pytest.mark.django_db
def test_product_must_map_to_published_knowledge_before_activation(django_user_model):
    owner = django_user_model.objects.create_user(
        username="product-owner", password="x", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Product provenance", objective="mapping", owner=owner
    )
    report = ResearchRuntime().create_report(project, "Report", "content", version=1)
    article = ResearchRuntime().draft_knowledge_from_report(report)
    article.published = True
    article.save(update_fields=["published"])
    product = Product.objects.create(
        title="Research service",
        product_type="service",
        price="100",
        owner=owner,
        knowledge_article=article,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/products/{product.pk}/activate/", {}, format="json")

    assert response.status_code == 202
    approval = ApprovalRequest.objects.get(
        target_type="Product", target_id=str(product.pk)
    )
    assert approval.action_type == "activate_product"
    product.refresh_from_db()
    assert product.active is False


@pytest.mark.django_db
def test_product_activation_requires_published_knowledge(django_user_model):
    owner = django_user_model.objects.create_user(
        username="product-owner-draft", password="x", is_staff=True
    )
    product = Product.objects.create(
        title="Draft service",
        product_type="service",
        price="100",
        owner=owner,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/products/{product.pk}/activate/", {}, format="json")

    assert response.status_code == 409
    assert ApprovalRequest.objects.filter(target_type="Product").count() == 0
    product.refresh_from_db()
    assert product.active is False


@pytest.mark.django_db
def test_owner_approval_activates_product(django_user_model):
    owner = django_user_model.objects.create_user(
        username="product-approver", password="x", is_staff=True
    )
    article = KnowledgeArticle.objects.create(
        title="Published knowledge",
        slug="published-knowledge",
        content="content",
        published=True,
    )
    product = Product.objects.create(
        title="Approved service",
        product_type="service",
        price="100",
        owner=owner,
        knowledge_article=article,
    )
    approval = ApprovalRequest.objects.create(
        action_type="activate_product",
        target_type="Product",
        target_id=str(product.pk),
        reason="Owner approval required",
        risk="high",
        requested_by=owner,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True, "note": "Activation approved"},
        format="json",
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.active is True
    approval.refresh_from_db()
    assert approval.status == "approved"
