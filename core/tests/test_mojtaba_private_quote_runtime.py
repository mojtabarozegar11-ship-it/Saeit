"""Six private, real cost-model artifacts through the existing economic task runner.

No customer, contact, money movement, external publication or accepted quotes.
"""
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import call_command

from core.models import Agent, AgentTask
from core.mojtaba_private_quote import prepare_private_quote, QuoteScenarioError


SCENARIO = {
    "currency": "IRT",
    "base_unit_price": "300000",
    "discount_percent": "0",
    "direct_unit_cost": "110000",
    "delivery_unit_cost": "20000",
    "payment_unit_fee": "5000",
    "refund_unit_reserve": "10000",
    "tax_unit_reserve": "20000",
    "period_fixed_cost": "1000000",
    "expected_units": 10,
}


@pytest.mark.django_db
@pytest.mark.parametrize("service_code", (
    "AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01",
))
def test_six_service_quote_scenarios_execute_with_actual_master_task(
        service_code, tmp_path):
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        call_command("seed_online_income_agents", verbosity=0)
        agent = Agent.objects.get(code="economic-master-agent")
        task = AgentTask.objects.create(
            agent=agent, action_type="income_quote_scenario",
            capability_code="income_quote_scenario", risk_snapshot="medium",
            status="queued",
            input_data={"service_code": service_code, "scenario": SCENARIO},
        )
        output = StringIO()
        call_command("run_economic_worker", task_id=task.pk, stdout=output)
        task.refresh_from_db()
        assert task.status == "completed"
        assert task.output_data["verified_effect"] is True
        assert task.output_data["price_approved"] is False
        assert task.output_data["external_payment_verified"] is False
        assert task.output_data["revenue_not_assessed"] is True
        files = list(tmp_path.rglob("QUOTE-*.md"))
        assert len(files) == 1
        assert files[0].name.startswith("QUOTE-" + service_code + "-")
        rendered = files[0].read_text(encoding="utf-8")
        assert "m o j t a b a" not in rendered
        assert "mojtaba.bot.ai" in rendered
        assert "حاشیه مشارکت" in rendered
        assert "300000" in rendered
        assert "پیش‌فاکتور" in rendered


def test_identical_costed_quote_is_idempotent_not_another_business_result(tmp_path):
    request = {"service_code": "WEB-01", "scenario": SCENARIO}
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        first = prepare_private_quote(request)
        second = prepare_private_quote(request)
    assert first["created"] is True and second["created"] is False
    assert first["input_sha256"] == second["input_sha256"]
    assert first["output_sha256"] == second["output_sha256"]
    assert first["quote_approved"] is False
    assert len(list(tmp_path.rglob("QUOTE-*.md"))) == 1


@pytest.mark.parametrize("bad", [
    {"service_code": "WEB-01", "scenario": {**SCENARIO, "customer_phone": "+98..." }},
    {"service_code": "OTHER", "scenario": SCENARIO},
    {"service_code": "WEB-01", "scenario": {**SCENARIO, "base_unit_price": -1}},
    {"service_code": "WEB-01", "scenario": {**SCENARIO, "currency": "USD/IRT"}},
    {"service_code": "WEB-01", "scenario": {**SCENARIO, "expected_units": True}},
    {"service_code": "WEB-01", "scenario": {**SCENARIO, "discount_percent": "101"}},
])
def test_invalid_or_personal_quote_input_fails_before_any_artifact(bad, tmp_path):
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        with pytest.raises(QuoteScenarioError):
            prepare_private_quote(bad)
    assert not list(tmp_path.rglob("QUOTE-*.md"))


def test_quote_zero_or_negative_margin_remains_private_and_unsellable(tmp_path):
    scenario = {**SCENARIO, "base_unit_price": "50000"}
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        result = prepare_private_quote({"service_code": "AGR-01",
                                        "scenario": scenario})
    assert result["created"] is True
    assert result["unit_economics_viable"] is False
    assert result["quote_approved"] is False
    assert result["external_settlement"] is None


def test_quote_does_not_reuse_world_readable_artifact(tmp_path):
    request = {"service_code": "AGR-01", "scenario": SCENARIO}
    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        assert prepare_private_quote(request)["created"] is True
        result = next(tmp_path.rglob("QUOTE-*.md"))
        result.chmod(0o644)
        with pytest.raises(QuoteScenarioError, match="QUOTE_UNSAFE_EXISTING"):
            prepare_private_quote(request)
        assert result.exists()


def test_quote_concurrent_writer_cannot_be_overwritten(tmp_path):
    request = {"service_code": "AGR-01", "scenario": SCENARIO}

    def conflicting_writer(src, dst, **kwargs):
        Path(dst).write_text("trusted older document", encoding="utf-8")
        raise FileExistsError("another writer")

    with patch("core.mojtaba_commercial_services.Path.home", return_value=tmp_path):
        with patch("core.mojtaba_private_quote.os.link", side_effect=conflicting_writer):
            with pytest.raises(QuoteScenarioError, match="QUOTE_CONCURRENT_COLLISION"):
                prepare_private_quote(request)
    reports = list(tmp_path.rglob("QUOTE-*.md"))
    assert len(reports) == 1
    assert reports[0].read_text(encoding="utf-8") == "trusted older document"
