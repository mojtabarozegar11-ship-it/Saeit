import pytest

from core.models import KnowledgeArticle, ResearchProject
from core.research_runtime import ResearchRuntime


@pytest.mark.django_db
def test_report_creates_unpublished_knowledge_draft_with_provenance(django_user_model):
    user = django_user_model.objects.create_user(username="knowledge-owner", password="x")
    project = ResearchProject.objects.create(title="Knowledge pipeline", objective="pipeline", owner=user)
    report = ResearchRuntime().create_report(project, "Research Report", {"summary": "verified"}, version=1)

    article = ResearchRuntime().draft_knowledge_from_report(report)

    assert article.source_report_id == report.id
    assert article.published is False
    assert article.slug == "research-report"
    assert article.content == str({"summary": "verified"})


@pytest.mark.django_db
def test_knowledge_slug_is_deterministic_and_collision_safe(django_user_model):
    user = django_user_model.objects.create_user(username="knowledge-owner-2", password="x")
    project = ResearchProject.objects.create(title="Knowledge pipeline", objective="pipeline", owner=user)
    runtime = ResearchRuntime()
    report1 = runtime.create_report(project, "Same Report", "one", version=1)
    report2 = runtime.create_report(project, "Same Report", "two", version=2)

    first = runtime.draft_knowledge_from_report(report1)
    second = runtime.draft_knowledge_from_report(report2)

    assert first.slug == "same-report"
    assert second.slug == "same-report-2"
    assert KnowledgeArticle.objects.count() == 2
