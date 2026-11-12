import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core import weather_agent
from core.models import Agent, AgentTask, NewsletterStory
from core.unified_bot_identity import BOT_CODE


pytestmark = pytest.mark.django_db


def _offline_weather_cycle(monkeypatch):
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: [
        {"forecast": [{"date": "2026-11-06"} for _ in range(7)]}
        for _ in weather_agent.PROVINCES
    ])
    monkeypatch.setattr(weather_agent, "build_public_report", lambda data: "Verified weather report")
    monkeypatch.setattr(weather_agent, "generate_research_contents", lambda summary: [])


def _bot():
    return Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", mission="Sole operational bot", active=True,
    )


def test_weather_does_not_publish_as_unrelated_agent_when_canonical_missing(monkeypatch):
    Agent.objects.create(code="trading-observer", name="Trading Observer", mission="market", active=True)
    def no_forecast(*args, **kwargs):
        raise AssertionError("weather network must not run before bot ownership gate")
    monkeypatch.setattr(weather_agent, "province_forecast", no_forecast)
    with pytest.raises(RuntimeError, match="MOJTABA_CANONICAL_AGENT_NOT_PROVISIONED"):
        weather_agent.run_daily_cycle()
    assert not NewsletterStory.objects.filter(fingerprint__startswith="weather-iran-").exists()


def test_weather_new_report_belongs_to_the_canonical_bot(monkeypatch):
    Agent.objects.create(code="trading-observer", name="Trading Observer", mission="market", active=True)
    owner = _bot()
    _offline_weather_cycle(monkeypatch)
    result = weather_agent.run_daily_cycle()
    assert NewsletterStory.objects.get(pk=result["weather_story_id"]).agent_id == owner.pk
    assert not Agent.objects.filter(code__in=("content-research", "content-director")).exists()


@pytest.mark.parametrize("legacy_code", ["content-research", "content-director"])
def test_active_legacy_content_worker_blocks_weather_before_external_io(monkeypatch, legacy_code):
    _bot()
    old = Agent.objects.create(code=legacy_code, name="Legacy", mission="Content", active=True)
    def no_forecast(*args, **kwargs):
        raise AssertionError("must not fetch forecasts while old worker is still active")
    monkeypatch.setattr(weather_agent, "province_forecast", no_forecast)
    with pytest.raises(RuntimeError, match="MOJTABA_LEGACY_HANDOFF_REQUIRED"):
        weather_agent.run_daily_cycle()
    old.refresh_from_db()
    assert old.active
    assert not NewsletterStory.objects.exists()


def test_inactive_legacy_with_queued_task_requires_handoff(monkeypatch):
    _bot()
    old = Agent.objects.create(
        code="content-research", name="Legacy Research", mission="Weather", active=False,
    )
    task = AgentTask.objects.create(agent=old, action_type="weather_report", status="queued")
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: pytest.fail("unexpected IO"))
    with pytest.raises(RuntimeError, match="MOJTABA_LEGACY_HANDOFF_REQUIRED"):
        weather_agent.run_daily_cycle()
    task.refresh_from_db()
    assert task.agent_id == old.pk and task.status == "queued"


def test_inactive_legacy_with_unpublished_story_requires_handoff(monkeypatch):
    _bot()
    old = Agent.objects.create(
        code="content-director", name="Legacy Content", mission="Weather", active=False,
    )
    story = NewsletterStory.objects.create(
        agent=old, story_type="report", title="Old review", slug="old-weather-review",
        summary="Previously prepared", body="Retain this draft",
        fingerprint="weather-previous-review", status="draft",
    )
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: pytest.fail("unexpected IO"))
    with pytest.raises(RuntimeError, match="MOJTABA_LEGACY_HANDOFF_REQUIRED"):
        weather_agent.run_daily_cycle()
    story.refresh_from_db()
    assert story.agent_id == old.pk and story.status == "draft"


def test_weather_api_key_alone_never_authorizes_paid_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("MOJ_PAID_LLM_ENABLED", "1")
    monkeypatch.delenv("MOJ_WEATHER_PAID_CONTENT_APPROVAL_DATE", raising=False)
    generated = weather_agent.generate_research_contents("Weather report")
    assert generated == []


def test_weather_does_not_regenerate_existing_daily_content(monkeypatch):
    _bot()
    _offline_weather_cycle(monkeypatch)
    calls = []

    def generate_once(report):
        calls.append(report)
        return [
            {"title": "Research item one", "body": "First original item"},
            {"title": "Research item two", "body": "Second original item"},
        ]
    monkeypatch.setattr(weather_agent, "generate_research_contents", generate_once)
    weather_agent.run_daily_cycle()
    weather_agent.run_daily_cycle()
    assert len(calls) == 1
    assert NewsletterStory.objects.filter(agent__code=BOT_CODE).count() == 3


def test_weather_does_not_publish_an_incomplete_31_province_report(monkeypatch):
    _bot()
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: [])
    with pytest.raises(RuntimeError, match="Incomplete seven-day weather forecast"):
        weather_agent.run_daily_cycle()
    assert not NewsletterStory.objects.filter(fingerprint__startswith="weather-iran-").exists()


def test_existing_historical_weather_story_keeps_original_agent_fk(monkeypatch):
    _bot()
    old = Agent.objects.create(code="content-research", name="Old", mission="Old", active=False)
    from django.utils import timezone
    day = timezone.localdate()
    old_story = NewsletterStory.objects.create(
        agent=old, story_type="report", title="Old weather",
        slug=f"weather-iran-{day.isoformat()}", summary="Old forecast",
        body="Archived source report", event_date=day,
        fingerprint=f"weather-iran-{day.isoformat()}",
        status="published", published_at=timezone.now(),
    )
    _offline_weather_cycle(monkeypatch)
    result = weather_agent.run_daily_cycle()
    old_story.refresh_from_db()
    assert result["weather_story_id"] == old_story.pk
    assert old_story.agent_id == old.pk


def test_weather_command_reports_handoff_block_not_success(monkeypatch):
    _bot()
    Agent.objects.create(
        code="content-director", name="Legacy Content",
        mission="Independent worker", active=True,
    )
    monkeypatch.setattr(
        weather_agent, "province_forecast",
        lambda days=7: pytest.fail("command must block before external weather IO"),
    )
    with pytest.raises(CommandError, match="WEATHER_MODULE_HANDOFF_BLOCKED"):
        call_command("weather_agent_cycle")
    assert not NewsletterStory.objects.exists()
