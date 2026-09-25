import pytest
from rest_framework.test import APIClient

from core.models import ApprovalRequest, KnowledgeArticle, ResearchProject
from core.research_runtime import ResearchRuntime


@pytest.mark.django_db
def test_publish_action_creates_pending_owner_approval(django_user_model):
    owner = django_user_model.objects.create_user(
        username="knowledge-publisher", password="x", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Publish pipeline", objective="approval", owner=owner
    )
    report = ResearchRuntime().create_report(
        project, "Approved report", {"summary": "ready"}, version=1
    )
    article = ResearchRuntime().draft_knowledge_from_report(report)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(f"/api/knowledge/{article.pk}/publish/", {}, format="json")

    assert response.status_code == 202
    approval = ApprovalRequest.objects.get(
        target_type="KnowledgeArticle", target_id=str(article.pk)
    )
    assert approval.status == "pending"
    article.refresh_from_db()
    assert article.published is False


@pytest.mark.django_db
def test_owner_approval_publishes_knowledge_article(django_user_model):
    owner = django_user_model.objects.create_user(
        username="knowledge-owner", password="x", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Publish pipeline", objective="approval", owner=owner
    )
    report = ResearchRuntime().create_report(
        project, "Approved report", "content", version=1
    )
    article = ResearchRuntime().draft_knowledge_from_report(report)
    approval = ApprovalRequest.objects.create(
        action_type="publish",
        target_type="KnowledgeArticle",
        target_id=str(article.pk),
        reason="Owner approval required",
        risk="high",
        requested_by=owner,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.post(
        f"/api/approvals/{approval.pk}/decide/",
        {"approved": True, "note": "Publish approved"},
        format="json",
    )

    assert response.status_code == 200
    article.refresh_from_db()
    approval.refresh_from_db()
    assert article.published is True
    assert approval.status == "approved"


@pytest.mark.django_db
def test_direct_published_flag_mutation_is_blocked(django_user_model):
    owner = django_user_model.objects.create_user(
        username="knowledge-edit", password="x", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Publish pipeline", objective="approval", owner=owner
    )
    report = ResearchRuntime().create_report(project, "Report", "content", version=1)
    article = ResearchRuntime().draft_knowledge_from_report(report)

    client = APIClient()
    client.force_authenticate(user=owner)
    response = client.patch(
        f"/api/knowledge/{article.pk}/",
        {"published": True},
        format="json",
    )

    assert response.status_code == 400
    article.refresh_from_db()
    assert article.published is False
