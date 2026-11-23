import pytest

from core import weather_agent
from core.models import Agent, NewsletterStory


pytestmark = pytest.mark.django_db


def _offline_weather_cycle(monkeypatch):
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: [
        {'forecast': [{'date': '2026-11-06'} for _ in range(7)]}
        for _ in weather_agent.PROVINCES
    ])
    monkeypatch.setattr(weather_agent, "build_public_report", lambda data: "Verified weather report")
    monkeypatch.setattr(weather_agent, "generate_research_contents", lambda summary: [])


def test_weather_does_not_publish_as_an_unrelated_active_agent(monkeypatch):
    Agent.objects.create(code="trading-observer", name="Trading Observer", mission="market", active=True)
    _offline_weather_cycle(monkeypatch)

    with pytest.raises(RuntimeError, match="CANONICAL_CONTENT_OWNER_NOT_ACTIVE"):
        weather_agent.run_daily_cycle()

    assert not NewsletterStory.objects.filter(fingerprint__startswith="weather-iran-").exists()


def test_weather_assigns_unpublished_report_to_the_canonical_bot(monkeypatch):
    Agent.objects.create(code="trading-observer", name="Trading Observer", mission="market", active=True)
    director = Agent.objects.create(code="content-director", name="Retired Director", mission="legacy", active=False)
    central = Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba Bot", mission="canonical", active=True)
    _offline_weather_cycle(monkeypatch)

    result = weather_agent.run_daily_cycle()

    story = NewsletterStory.objects.get(pk=result["weather_story_id"])
    assert story.agent_id == central.id
    assert story.status == "draft"
    assert story.published_at is None
    director.refresh_from_db()
    assert director.active is False


def test_weather_api_key_alone_never_authorizes_paid_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("MOJ_PAID_LLM_ENABLED", "1")
    monkeypatch.delenv("MOJ_WEATHER_PAID_CONTENT_APPROVAL_DATE", raising=False)

    generated = weather_agent.generate_research_contents("Weather report")

    assert generated == []  # No paid call and no daily repost of identical text.


def test_weather_same_day_flags_never_spend_without_one_use_grant(monkeypatch):
    from django.utils import timezone
    import sys
    import types

    class ForbiddenModelClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("paid model initialized without one-use grant")

    monkeypatch.setenv("OPENAI_API_KEY", "present-but-not-authorized")
    monkeypatch.setenv("MOJ_PAID_LLM_ENABLED", "1")
    monkeypatch.setenv("MOJ_WEATHER_PAID_CONTENT_APPROVAL_DATE", timezone.localdate().isoformat())
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=ForbiddenModelClient))

    assert weather_agent.generate_research_contents("Source-specific daily forecast") == []


def test_weather_does_not_regenerate_existing_daily_content(monkeypatch):
    Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba Bot", mission="content", active=True)
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


def test_weather_does_not_publish_an_incomplete_31_province_report(monkeypatch):
    Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba Bot", mission="content", active=True)
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: [])
    with pytest.raises(RuntimeError, match='Incomplete seven-day weather forecast'):
        weather_agent.run_daily_cycle()
    assert not NewsletterStory.objects.filter(fingerprint__startswith='weather-iran-').exists()


def test_legacy_content_agent_cannot_authorize_weather_or_network(monkeypatch):
    Agent.objects.create(code="content-director", name="Old Content", mission="legacy", active=True)
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: (_ for _ in ()).throw(AssertionError("network attempted")))
    with pytest.raises(RuntimeError, match="CANONICAL_CONTENT_OWNER_NOT_ACTIVE"):
        weather_agent.run_daily_cycle()
    assert not NewsletterStory.objects.exists()


def test_repeat_weather_cycle_never_overwrites_a_reviewed_story(monkeypatch):
    Agent.objects.create(code="mojtaba-bot-ai", name="Mojtaba Bot", mission="content", active=True)
    _offline_weather_cycle(monkeypatch)
    first = weather_agent.run_daily_cycle()
    story = NewsletterStory.objects.get(pk=first["weather_story_id"])
    story.body = "Reviewed immutable editorial text"
    story.status = "approved"
    story.save(update_fields=["body", "status"])
    weather_agent.run_daily_cycle()
    story.refresh_from_db()
    assert story.body == "Reviewed immutable editorial text"
    assert story.status == "approved"


def test_met_norway_terms_must_be_human_accepted_before_network_or_cache(monkeypatch):
    monkeypatch.delenv("MOJ_MET_NORWAY_TOS_ACCEPTED_BY_OWNER", raising=False)
    monkeypatch.setattr(
        weather_agent, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("external API accessed")),
    )
    monkeypatch.setattr(
        weather_agent.cache, "get",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("weather cache accessed")),
    )
    with pytest.raises(RuntimeError, match="MET_NORWAY_OWNER_TOS_ACCEPTANCE_REQUIRED"):
        weather_agent._fetch(35.6892, 51.3890)


def test_met_norway_tos_false_like_values_are_not_authorizations(monkeypatch):
    monkeypatch.setattr(
        weather_agent, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("external API accessed")),
    )
    for value in ("", "0", "false", "True", "approved-by-agent"):
        monkeypatch.setenv("MOJ_MET_NORWAY_TOS_ACCEPTED_BY_OWNER", value)
        with pytest.raises(RuntimeError, match="MET_NORWAY_OWNER_TOS_ACCEPTANCE_REQUIRED"):
            weather_agent._fetch(35.6892, 51.3890)
