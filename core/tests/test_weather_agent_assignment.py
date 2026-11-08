import pytest

from core import weather_agent
from core.editorial_signature import has_final_signature
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

    with pytest.raises(RuntimeError, match="No active content agent"):
        weather_agent.run_daily_cycle()

    assert not NewsletterStory.objects.filter(fingerprint__startswith="weather-iran-").exists()


def test_weather_assigns_report_to_content_director(monkeypatch):
    Agent.objects.create(code="trading-observer", name="Trading Observer", mission="market", active=True)
    director = Agent.objects.create(code="content-director", name="Content Director", mission="content", active=True)
    _offline_weather_cycle(monkeypatch)

    result = weather_agent.run_daily_cycle()

    story = NewsletterStory.objects.get(pk=result["weather_story_id"])
    assert story.agent_id == director.id
    assert has_final_signature(story.body)


def test_weather_api_key_alone_never_authorizes_paid_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("MOJ_PAID_LLM_ENABLED", "1")
    monkeypatch.delenv("MOJ_WEATHER_PAID_CONTENT_APPROVAL_DATE", raising=False)

    generated = weather_agent.generate_research_contents("Weather report")

    assert generated == []  # No paid call and no daily repost of identical text.


def test_weather_does_not_regenerate_existing_daily_content(monkeypatch):
    Agent.objects.create(code="content-director", name="Content Director", mission="content", active=True)
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
    Agent.objects.create(code="content-director", name="Content Director", mission="content", active=True)
    monkeypatch.setattr(weather_agent, "province_forecast", lambda days=7: [])
    with pytest.raises(RuntimeError, match='Incomplete seven-day weather forecast'):
        weather_agent.run_daily_cycle()
    assert not NewsletterStory.objects.filter(fingerprint__startswith='weather-iran-').exists()
