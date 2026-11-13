"""Only the existing master can audit its own archived research watch states."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
from django.core.management import call_command

from core.models import Agent, AgentTask
from core.tool_gateway import ToolGatewayError


def make_review(t0, close, serial, stance="watch_buy"):
    generated = t0 + timedelta(minutes=5)
    reviewed = t0 + timedelta(minutes=7)
    return {
        "reviewed_at": reviewed,
        "report": {
            "schema": "mojtaba.bot.ai.private-market-research-review.v1",
            "canonical_agent": "economic-master-agent",
            "source_sha256": f"{serial:064x}",
            "source_bytes": 400,
            "observation_generated_at": generated.isoformat(),
            "observation_expires_at": (generated + timedelta(minutes=90)).isoformat(),
            "measurement": {"verified_observation_count": 2},
            "controls": {
                "research_only": True, "execution": "disabled", "orders": 0,
                "publication_enabled": False, "delivery_enabled": False,
                "financial_actions_enabled": False,
            },
            "observations": [
                {"symbol": sym, "stance": decision, "data_source": provider,
                 "observed_at": t0.isoformat(), "signal_id": f"{serial}-{sym}",
                 "method": "sma20-sma50-momentum10-v1-closed-1h",
                 "reference_close_usd": price}
                for sym, price, decision, provider in (
                    ("BTC/USD", close, stance, "bitstamp-public-ohlc"),
                    ("ETH/USD", 200, "neutral", "kraken-spot-public-ohlc"),
                )
            ],
        },
    }


@pytest.mark.django_db
def test_forward_model_is_single_master_task_with_zero_orders(monkeypatch):
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    master = Agent.objects.get(code="economic-master-agent")
    capability = master.capabilities.get(code="income_mojtrade_forward_audit")
    t0 = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
    history = [make_review(t0, 100, 1), make_review(t0 + timedelta(hours=1), 104, 2, "neutral")]
    rows = []
    for snapshot in history:
        task = AgentTask.objects.create(
            agent=master, status="completed",
            action_type="income_mojtrade_research_review",
            capability_code="income_mojtrade_research_review",
            execution_id=f"completed-{len(rows)}", attempt_count=1,
            output_data={
                "verified_effect": True,
                "action_performed": "Observed a finished USD candle in private review",
                "evidence": {"kind": "mojtrade_private_research_review",
                             "value": copy.deepcopy(snapshot["report"])},
            },
        )
        AgentTask.objects.filter(pk=task.pk).update(updated_at=snapshot["reviewed_at"])
        rows.append(task)
    audit = AgentTask.objects.create(
        agent=master, action_type=capability.code, capability_code=capability.code,
        risk_snapshot=capability.risk_level, status="queued", input_data={},
    )
    call_command("run_economic_worker", task_id=audit.pk)
    audit.refresh_from_db()
    report = audit.output_data["evidence"]["value"]
    assert audit.status == "completed"
    assert audit.output_data["verified_effect"] is True
    assert report["eligible_hypothetical_one_hour_pairs"] == 1
    assert report["recent_reference_samples"][0]["modeled_net_return_pct"] == "3.7000"
    assert report["verified_trade_pnl"] is None
    assert report["collected_revenue"] is None
    assert report["orders"] == 0
    assert Agent.objects.filter(code="economic-master-agent").count() == 1
    assert AgentTask.objects.filter(pk__in=[t.pk for t in rows], status="completed").count() == 2


@pytest.mark.django_db
def test_other_agent_cannot_invoke_forward_audit_or_get_capability(monkeypatch):
    from core.economic_tool_pack import build_economic_gateway
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    call_command("seed_online_income_agents")
    other = Agent.objects.get(code="moj_1ro_1")
    assert not other.capabilities.filter(code="income_mojtrade_forward_audit").exists()
    task = AgentTask.objects.create(
        agent=other, status="running",
        action_type="income_mojtrade_forward_audit",
        capability_code="income_mojtrade_forward_audit",
        execution_id="no-authority", attempt_count=1,
    )
    with pytest.raises(ToolGatewayError, match="capability"):
        build_economic_gateway().invoke(
            "income_mojtrade_forward_audit", {},
            task_id=task.pk, execution_id="no-authority",
        )


@pytest.mark.django_db
def test_forward_audit_rejects_custom_prices_and_orders(monkeypatch):
    from core.mojtrade_forward_audit import master_forward_audit
    from core.mojtrade_forward_metrics import ForwardEvidenceError
    monkeypatch.setenv("MOJ_FACTORY_LOCAL_MODE", "1")
    for forbidden in ({"price": 100}, {"order": "buy"}, {"fee_bps": 0},
                      {"source_path": "/tmp/forged.json"}):
        with pytest.raises(ForwardEvidenceError, match="NO_CALLER_CONTROLLED"):
            master_forward_audit(forbidden)
