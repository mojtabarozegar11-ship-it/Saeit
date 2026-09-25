import pytest
from datetime import date

from core.daily_content_agent import DailyContentAgent, DailyContentPlanner
from core.daily_content_models import DailyContentDraft, DailyContentPlan
from core.models import KnowledgeArticle, ResearchProject


@pytest.mark.django_db
def test_daily_plan_has_two_question_slots(django_user_model):
    owner = django_user_model.objects.create_user(username="daily-owner", password="x")
    project = ResearchProject.objects.create(title="Site", objective="content", owner=owner)
    plan = DailyContentPlanner().ensure_plan(project, date(2026, 9, 25))
    drafts = DailyContentAgent().prepare(project, date(2026, 9, 25), company_content="company", ceo_content="ceo")
    assert DailyContentPlan.objects.count() == 1
    assert len(drafts) == 2
    assert all(item.title.endswith("؟") for item in drafts)
    assert {item.kind for item in drafts} == {"company", "ceo"}
    assert plan.company_topic
    assert plan.ceo_topic


@pytest.mark.django_db
def test_daily_drafts_are_distinct_and_unpublished(django_user_model):
    owner = django_user_model.objects.create_user(username="daily-owner-2", password="x")
    project = ResearchProject.objects.create(title="Site", objective="content", owner=owner)
    drafts = DailyContentAgent().prepare(project, date(2026, 9, 25), company_content="A", ceo_content="B")
    assert drafts[0].title != drafts[1].title
    article = DailyContentAgent.publish_ready_article(drafts[0], owner)
    assert isinstance(article, KnowledgeArticle)
    assert article.published is False
    drafts[0].refresh_from_db()
    assert drafts[0].status == "approval_pending"
