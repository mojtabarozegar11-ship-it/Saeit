"""MojTrade research is a real canonical AgentTask, never an order executor."""
from datetime import timedelta
from io import StringIO
import json
import os

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_bridge import MojTradeBridgeError, ingest_private_observation
from core.unified_bot_identity import (
    BOT_CODE, MOJTRADE_RESEARCH_CAPABILITY, module_for_capability,
)


@pytest.fixture
def canonical_market(tmp_path, settings):
    call_command("seed_online_income_agents", stdout=StringIO())
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    settings.MOJTRADE_PRIVATE_DIR = str(root)
    now = timezone.now().replace(microsecond=0)
    generated = now - timedelta(minutes=1)
    observed = now - timedelta(hours=1)
    payload = {
        "schema_version": 1,
        "source": "mojtrade-vps",
        "generated_at": generated.isoformat(),
        "expires_at": (now + timedelta(minutes=60)).isoformat(),
        "signals": [
            {
                "id": "a" * 24, "market": "crypto", "symbol": "BTC/USD",
                "timeframe": "1h", "stance": "watch_buy",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "coinbase-exchange-public-candles",
            },
            {
                "id": "b" * 24, "market": "crypto", "symbol": "ETH/USD",
                "timeframe": "1h", "stance": "neutral",
                "observed_at": observed.isoformat(),
                "method": "sma20-sma50-momentum10-v1-closed-1h",
                "data_source": "bitstamp-public-ohlc",
            },
        ],
    }
    source = root / "validated-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(source, 0o600)
    return root, source, payload


@pytest.mark.django_db
def test_market_receipt_is_owned_by_one_bot_and_has_no_execution(canonical_market):
    output = StringIO()
    call_command("mojtrade_research_cycle", stdout=output)
    assert "new_receipt=1" in output.getvalue()
    assert "orders=0" in output.getvalue()
    assert "execution=disabled" in output.getvalue()
    task = AgentTask.objects.get(capability_code=MOJTRADE_RESEARCH_CAPABILITY)
    assert task.agent.code == BOT_CODE
    assert task.agent.active
    assert task.action_type == MOJTRADE_RESEARCH_CAPABILITY
    assert task.status == "completed"
    assert task.attempt_count == 1
    assert task.cost == 0
    assert task.output_data["verified_effect"] is True
    assert task.output_data["execution"] == "disabled"
    assert task.output_data["orders"] == 0
    assert task.output_data["broker_connected"] is False
    assert task.output_data["published"] is False
    assert task.output_data["revenue_verified"] is False
    review = task.output_data["strategy_risk_review"]
    assert review["schema"] == "mojtrade-research-gate-v1"
    assert review["setup_candidates_not_trades"] == 1
    assert review["decisions"][0]["classification"] == "monitor_bullish"
    assert review["decisions"][1]["classification"] == "no_setup"
    assert review["risk_gate"] == "blocked_missing_broker_verified_inputs"
    assert review["executable_order_intents"] == []
    assert review["broker_connected"] is False
    assert review["orders"] == 0 and review["execution"] == "disabled"
    assert len(review["decision_digest_sha256"]) == 64
    assert len(task.output_data["market_observations"]) == 2
    assert task.output_data["market_observations"][1]["data_source"] == "bitstamp-public-ohlc"
    assert "validated-payload.json" not in json.dumps(task.input_data)
    assert not task.agent.capabilities.filter(code__in=["trade", "payment", "withdraw", "deploy"]).exists()
    # Existing Django migrations seed unrelated agent records; the bridge must
    # not create an extra MojTrade executor identity.
    assert Agent.objects.filter(code=BOT_CODE).count() == 1
    assert not Agent.objects.filter(code__startswith="mojtrade").exists()
    assert module_for_capability(MOJTRADE_RESEARCH_CAPABILITY) == "mojtrade_private_research"
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="task_claimed").count() == 1
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="task_completed").count() == 1
    assert AuditLog.objects.filter(target_type="AgentTask", target_id=str(task.pk), action="mojtrade_private_research_ingested").count() == 1


@pytest.mark.django_db
def test_reprocessing_same_snapshot_is_idempotent_and_does_not_make_new_receipts(canonical_market):
    first, created = ingest_private_observation()
    second, created_again = ingest_private_observation()
    assert created is True and created_again is False
    assert first.pk == second.pk
    assert AgentTask.objects.filter(capability_code=MOJTRADE_RESEARCH_CAPABILITY).count() == 1
    assert AuditLog.objects.filter(action="mojtrade_private_research_ingested").count() == 1


@pytest.mark.django_db
def test_economic_worker_does_not_claim_or_misclassify_market_research(canonical_market):
    agent = Agent.objects.get(code=BOT_CODE)
    pending = AgentTask.objects.create(
        agent=agent, action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        risk_snapshot="low", status="queued",
    )
    output = StringIO()
    call_command("run_economic_worker", stdout=output)
    assert "IDLE: no queued economic task." in output.getvalue()
    assert "BLOCKED_UNSUPPORTED" not in output.getvalue()
    output = StringIO()
    call_command("online_income_cycle", "--dry-run", stdout=output)
    assert f"BRAIN_CONTINUE task={pending.pk}" not in output.getvalue()
    pending.refresh_from_db()
    assert pending.status == "queued" and pending.attempt_count == 0


@pytest.mark.django_db
def test_market_research_cannot_execute_concurrently_with_other_unified_work(canonical_market):
    agent = Agent.objects.get(code=BOT_CODE)
    AgentTask.objects.create(
        agent=agent, action_type="income_market_research",
        capability_code="income_market_research",
        status="running", execution_id="other-running-worker",
    )
    with pytest.raises(ValueError, match="already has a running task"):
        ingest_private_observation()
    assert AgentTask.objects.count() == 1
    assert not AuditLog.objects.filter(action="mojtrade_private_research_ingested").exists()


@pytest.mark.django_db
def test_noncompleted_duplicate_requires_reconciliation(canonical_market):
    task, _ = ingest_private_observation()
    task.status = "blocked"
    task.save(update_fields=["status"])
    with pytest.raises(MojTradeBridgeError, match="requires_reconciliation"):
        ingest_private_observation()
    assert AgentTask.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["expired", "future", "forged_method", "forged_id", "binance_usdt", "old_candle"])
def test_invalid_market_data_cannot_create_canonical_task(canonical_market, condition):
    _, source, payload = canonical_market
    if condition == "expired":
        payload["expires_at"] = (timezone.now() - timedelta(seconds=1)).isoformat()
    elif condition == "future":
        payload["generated_at"] = (timezone.now() + timedelta(minutes=3)).isoformat()
    elif condition == "forged_method":
        payload["signals"][0]["method"] = "fake_model_trade_now"
    elif condition == "forged_id":
        payload["signals"][0]["id"] = "external-order-id"
    elif condition == "binance_usdt":
        payload["signals"][0]["data_source"] = "binance-public-klines"
    else:
        payload["signals"][0]["observed_at"] = (timezone.now() - timedelta(days=2)).isoformat()
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MojTradeBridgeError):
        ingest_private_observation()
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["unconfigured", "world_readable", "symlink", "public_directory"])
def test_private_source_security_is_fail_closed(canonical_market, settings, tmp_path, condition):
    root, source, payload = canonical_market
    if condition == "unconfigured":
        settings.MOJTRADE_PRIVATE_DIR = ""
    elif condition == "world_readable":
        os.chmod(source, 0o644)
    elif condition == "symlink":
        original = root / "original.json"
        source.rename(original)
        source.symlink_to(original)
    else:
        os.chmod(root, 0o755)
    with pytest.raises(MojTradeBridgeError):
        ingest_private_observation()
    assert not AgentTask.objects.exists()


@pytest.mark.django_db
def test_unseeded_bot_does_not_autocreate_agents_or_approve_trade(canonical_market):
    Agent.objects.filter(code=BOT_CODE).update(active=False)
    with pytest.raises(MojTradeBridgeError, match="canonical_bot_is_not_active"):
        ingest_private_observation()
    assert not AgentTask.objects.exists()
