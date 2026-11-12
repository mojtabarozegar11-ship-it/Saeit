"""No weather-content model spend without a real, one-time owner-approved grant."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.approval import ApprovalService
from core.models import ApprovalRequest, NewsletterStory
from core import weather_agent


pytestmark = pytest.mark.django_db


def _grant(*, target_date=None, model="gpt-5.6", scope_override=None):
    day = timezone.localdate().isoformat()
    owner = get_user_model().objects.create_user(username="weather-owner")
    approval = ApprovalRequest.objects.create(
        action_type="weather_research_generation",
        target_type="MojtabaWeatherCycle",
        target_id=target_date or day,
        status="approved",
        reason="Specific one-time owner approval for one weather model request",
        risk="high",
        requested_by=owner,
    )
    scope = {
        "action": "weather_research_generation",
        "owner_bot_id": "mojtaba.bot.ai",
        "date": day,
        "model": model,
        "max_model_calls": 1,
        "max_articles": 2,
    }
    scope.update(scope_override or {})
    return ApprovalService().issue_grant(approval.pk, owner.pk, scope)


def test_environment_flags_never_enable_paid_call_without_grant(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    monkeypatch.setenv("MOJ_PAID_LLM_ENABLED", "1")
    monkeypatch.setenv("MOJ_WEATHER_PAID_CONTENT_APPROVAL_DATE", timezone.localdate().isoformat())
    with patch("openai.OpenAI") as model:
        assert weather_agent.generate_research_contents("public data") == []
    model.assert_not_called()


def test_correct_one_time_grant_consumes_before_single_paid_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    monkeypatch.setenv("OPENAI_WEATHER_CONTENT_MODEL", "gpt-5.6")
    grant = _grant()
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({"contents": [{"title": "One reviewed draft"}]})
        ))]
    )
    with patch("openai.OpenAI", return_value=client) as model:
        items = weather_agent.generate_research_contents("Weather evidence", approval_grant_id=grant.pk)
        assert items[0]["title"] == "One reviewed draft"
        model.assert_called_once_with(api_key="ci-test-key")
        client.chat.completions.create.assert_called_once()
        assert client.chat.completions.create.call_args.kwargs["max_completion_tokens"] == 5000
        with pytest.raises(RuntimeError, match="WEATHER_PAID_GRANT_INVALID_OR_CONSUMED"):
            weather_agent.generate_research_contents("Weather evidence", approval_grant_id=grant.pk)
        client.chat.completions.create.assert_called_once()
    grant.refresh_from_db()
    assert grant.used_at is not None


@pytest.mark.parametrize("scope_override", [
    {"owner_bot_id": "some-other-bot"},
    {"date": "1901-01-01"},
    {"model": "gpt-4o-mini"},
    {"max_model_calls": 2},
    {"max_articles": 10},
])
def test_wrong_grant_scope_never_invokes_model(monkeypatch, scope_override):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    monkeypatch.setenv("OPENAI_WEATHER_CONTENT_MODEL", "gpt-5.6")
    grant = _grant(scope_override=scope_override)
    with patch("openai.OpenAI") as model, pytest.raises(
        RuntimeError, match="WEATHER_PAID_GRANT_INVALID_OR_CONSUMED"
    ):
        weather_agent.generate_research_contents("Evidence", approval_grant_id=grant.pk)
    model.assert_not_called()
    grant.refresh_from_db()
    assert grant.used_at is None


def test_wrong_date_grant_blocks_before_any_forecast_request_or_publication(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    grant = _grant(target_date="1901-01-01")
    monkeypatch.setattr(
        weather_agent, "province_forecast",
        lambda days=7: pytest.fail("invalid grant must not reach external forecast API"),
    )
    with patch("openai.OpenAI") as model, pytest.raises(
        RuntimeError, match="WEATHER_PAID_GRANT_TARGET_NOT_APPROVED"
    ):
        weather_agent.run_daily_cycle(approval_grant_id=grant.pk)
    assert not NewsletterStory.objects.exists()
    model.assert_not_called()


def test_grant_rejected_after_issuance_does_not_spend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    grant = _grant()
    grant.approval.status = "rejected"
    grant.approval.save(update_fields=["status"])
    with patch("openai.OpenAI") as model, pytest.raises(
        RuntimeError, match="WEATHER_PAID_GRANT_TARGET_NOT_APPROVED"
    ):
        weather_agent.generate_research_contents("Evidence", approval_grant_id=grant.pk)
    model.assert_not_called()


def test_expired_grant_does_not_spend(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "ci-test-key")
    grant = _grant()
    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save(update_fields=["expires_at"])
    with patch("openai.OpenAI") as model, pytest.raises(
        RuntimeError, match="WEATHER_PAID_GRANT_INVALID_OR_CONSUMED"
    ):
        weather_agent.generate_research_contents("Evidence", approval_grant_id=grant.pk)
    model.assert_not_called()
