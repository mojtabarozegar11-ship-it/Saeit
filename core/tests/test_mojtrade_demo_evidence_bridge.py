"""cTrader demo evidence is a real single-bot audited task, not income."""
from io import StringIO
import os

import pytest
from django.core.management import call_command
from django.db.models import F

from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_demo_evidence_bridge import (
    DemoEvidenceBridgeError, ingest_private_demo_evidence,
)
from core.unified_bot_identity import (
    BOT_CODE, MOJTRADE_DEMO_AUDIT_CAPABILITY, module_for_capability,
)


SESSION = "0123456789abcdef0123456789abcdef"
LOG = (
    "MOJTRADE_AUDIT_V1|START|session=" + SESSION +
    "|alias=LITE_DEMO_1|currency=USD|symbol=XAUUSD|mode=demo|count=2\n"
    "MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION +
    "|deal_id=2026123456|position_id=32145|closed_utc=2026-11-10T11:00:00.0000000Z|side=buy|lots=0.01|gross=12|commission=-1|swap=-0.5|net=10.5|balance_after=10010.5\n"
    "MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION +
    "|deal_id=2026123457|position_id=32146|closed_utc=2026-11-10T11:01:00.0000000Z|side=sell|lots=0.02|gross=-7|commission=-1|swap=-0.2|net=-8.2|balance_after=10002.3\n"
    "MOJTRADE_AUDIT_V1|END|session=" + SESSION +
    "|count=2|wins=1|gross=5|commission=-2|swap=-0.7|net=2.3|demo_only=true|external_broker_reconciliation=false\n"
)


@pytest.fixture
def demo_evidence(tmp_path, settings):
    call_command("seed_online_income_agents", stdout=StringIO())
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    settings.MOJTRADE_PRIVATE_DIR = str(root)
    path = root / "demo-audit.log"
    path.write_text(LOG, encoding="utf-8")
    os.chmod(path, 0o600)
    return root, path


@pytest.mark.django_db
def test_canonical_demo_receipts_are_real_audited_tasks_not_real_income(demo_evidence):
    output = StringIO()
    call_command("mojtrade_demo_audit_cycle", stdout=output)
    assert "new_receipt=1" in output.getvalue()
    assert "orders=0" in output.getvalue()
    assert "real_revenue_verified=false" in output.getvalue()
    task = AgentTask.objects.get(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY)
    assert task.agent.code == BOT_CODE and task.status == "completed"
    assert task.risk_snapshot == "low"
    assert task.cost == 0
    assert task.output_data["verified_effect"] is True
    assert task.output_data["action_performed"] == "canonical_ctrader_demo_deal_evidence_ingested"
    assert task.output_data["demo_trading_history"]["closing_deal_count"] == 2
    assert task.output_data["demo_trading_history"]["broker_reported_net_account_currency"] == "2.3"
    assert task.output_data["demo_trading_history"]["mode"] == "demo"
    assert task.output_data["revenue_verified"] is False
    assert task.output_data["profit_verified"] is False
    assert task.output_data["demo_receipts_not_additive_between_snapshots"] is True
    assert task.output_data["broker_statement_reconciled"] is False
    assert task.output_data["source_log_is_independently_authenticated"] is False
    assert task.output_data["orders"] == 0
    assert len(task.input_data["source_sha256"]) == 64
    assert not Agent.objects.filter(code__startswith="mojtrade").exists()
    assert module_for_capability(MOJTRADE_DEMO_AUDIT_CAPABILITY) == "mojtrade_demo_execution_evidence"
    assert AuditLog.objects.filter(action="mojtrade_demo_closed_deals_audited", target_id=str(task.pk)).count() == 1


@pytest.mark.django_db
def test_identical_log_idempotently_reuses_canonical_receipt(demo_evidence):
    task, first = ingest_private_demo_evidence()
    same, second = ingest_private_demo_evidence()
    assert first is True and second is False
    assert task.pk == same.pk
    assert AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).count() == 1
    assert AuditLog.objects.filter(action="mojtrade_demo_closed_deals_audited").count() == 1


@pytest.mark.django_db
def test_demo_task_is_not_executed_by_unrelated_economic_worker(demo_evidence):
    agent = Agent.objects.get(code=BOT_CODE)
    pending = AgentTask.objects.create(
        agent=agent,
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        status="queued", risk_snapshot="low",
    )
    out = StringIO()
    call_command("run_economic_worker", stdout=out)
    assert "IDLE: no queued economic task" in out.getvalue()
    assert "BLOCKED_UNSUPPORTED" not in out.getvalue()
    pending.refresh_from_db()
    assert pending.status == "queued" and pending.attempt_count == 0


@pytest.mark.django_db
@pytest.mark.parametrize("condition", ["unconfigured", "open_directory", "public_file", "symlink", "forged_net"])
def test_unsafe_untrusted_or_forged_demo_receipts_do_not_mutate_db(
    demo_evidence, settings, condition,
):
    root, path = demo_evidence
    if condition == "unconfigured":
        settings.MOJTRADE_PRIVATE_DIR = ""
    elif condition == "open_directory":
        os.chmod(root, 0o755)
    elif condition == "public_file":
        os.chmod(path, 0o644)
    elif condition == "symlink":
        original = root / "original.log"
        path.rename(original)
        path.symlink_to(original)
    else:
        path.write_text(LOG.replace("|net=2.3|demo_only=", "|net=1000|demo_only="))
    with pytest.raises(DemoEvidenceBridgeError):
        ingest_private_demo_evidence()
    assert not AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).exists()
    assert not AuditLog.objects.filter(action="mojtrade_demo_closed_deals_audited").exists()


@pytest.mark.django_db
def test_running_canonical_task_blocks_another_demo_ledger_ingest(demo_evidence):
    agent = Agent.objects.get(code=BOT_CODE)
    AgentTask.objects.create(
        agent=agent, action_type="income_market_research",
        capability_code="income_market_research",
        status="running", execution_id="another-worker",
    )
    with pytest.raises(ValueError, match="already has a running task"):
        ingest_private_demo_evidence()
    assert not AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).exists()


@pytest.mark.django_db
def test_inactive_bot_cannot_pretend_demo_results_were_applied(demo_evidence):
    Agent.objects.filter(code=BOT_CODE).update(active=False)
    with pytest.raises(DemoEvidenceBridgeError, match="canonical_bot_not_active"):
        ingest_private_demo_evidence()
    assert not AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).exists()


@pytest.mark.django_db
def test_incomplete_duplicate_requires_reconciliation(demo_evidence):
    task, _ = ingest_private_demo_evidence()
    task.status = "blocked"
    task.save(update_fields=["status"])
    with pytest.raises(DemoEvidenceBridgeError, match="needs_reconciliation"):
        ingest_private_demo_evidence()
    assert AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).count() == 1
