"""Existing Economic Master Agent integrates read-only research, never orders."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from django.core.management import call_command

from core.models import Agent, AgentTask


@pytest.mark.django_db
def test_master_executes_private_market_review_as_one_economic_task(monkeypatch, tmp_path):
    from core.mojtrade_research_review import trusted_source

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    source = trusted_source()
    source.parent.mkdir(parents=True, mode=0o700)
    os.chmod(source.parent, 0o700)
    now = datetime.now(timezone.utc)
    generated = now - timedelta(minutes=5)
    observed = now - timedelta(minutes=80)
    source.write_text(json.dumps({
        "schema_version": 1, "source": "mojtrade-vps",
        "generated_at": generated.isoformat(),
        "expires_at": (generated + timedelta(minutes=90)).isoformat(),
        "signals": [
            {"id": ident, "market": "crypto", "symbol": symbol,
             "timeframe": "1h", "stance": "neutral",
             "observed_at": observed.isoformat(), "method": "sma20-sma50-momentum10-v1-closed-1h",
             "data_source": source_name}
            for ident, symbol, source_name in (
                ("btc", "BTC/USD", "bitstamp-public-ohlc"),
                ("eth", "ETH/USD", "kraken-spot-public-ohlc"),
            )
        ],
    }))
    os.chmod(source, 0o600)
    original = source.read_bytes()

    call_command("seed_online_income_agents")
    agent = Agent.objects.get(code="economic-master-agent")
    capability = agent.capabilities.get(code="income_mojtrade_research_review")
    task = AgentTask.objects.create(
        agent=agent, action_type=capability.code, capability_code=capability.code,
        risk_snapshot=capability.risk_level, status="queued", input_data={},
    )
    call_command("run_economic_worker", task_id=task.pk)
    task.refresh_from_db()
    assert task.status == "completed"
    assert task.output_data["verified_effect"] is True
    evidence = task.output_data["evidence"]["value"]
    assert evidence["measurement"]["forward_outcome_samples"] == 0
    assert evidence["measurement"]["verified_net_pnl"] is None
    assert evidence["controls"]["orders"] == 0
    assert task.output_data["verified_revenue"] is None
    assert source.read_bytes() == original
    assert Agent.objects.filter(code="economic-master-agent").count() == 1


@pytest.mark.django_db
def test_master_research_capability_denied_to_other_agent(monkeypatch, tmp_path):
    from core.tool_gateway import ToolGatewayError
    from core.economic_tool_pack import build_economic_gateway

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    other = Agent.objects.get(code="moj_1ro_1")
    assert not other.capabilities.filter(code="income_mojtrade_research_review").exists()
    gateway = build_economic_gateway()
    task = AgentTask.objects.create(
        agent=other, action_type="income_mojtrade_research_review",
        capability_code="income_mojtrade_research_review",
        status="running", execution_id="fake-no-authority", attempt_count=1,
    )
    with pytest.raises(ToolGatewayError, match="capability"):
        gateway.invoke("income_mojtrade_research_review", {},
                       task_id=task.pk, execution_id="fake-no-authority")
