"""Canonical cTrader demo statement cross-check is not real trading."""
import csv
import hashlib
from io import StringIO
import json
import os

import pytest
from django.core.management import call_command

from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_demo_evidence_bridge import ingest_private_demo_evidence
from core.mojtrade_readiness import trading_readiness_report
from core.mojtrade_statement_bridge import (
    DemoStatementBridgeError, ingest_demo_statement_crosscheck,
)
from core.unified_bot_identity import BOT_CODE, MOJTRADE_DEMO_AUDIT_CAPABILITY
from trading.mojtrade_broker_statement_check import FIELDS


SESSION = "0123456789abcdef0123456789abcdef"
DEALS = [
    {
        "deal_id": "2026123456", "position_id": "32145",
        "closed_utc": "2026-11-10T11:00:00.0000000Z",
        "symbol": "XAUUSD", "label": "MojTrade-OMEGA-X-DEMO", "side": "buy",
        "lots": "0.01", "gross": "12", "commission": "-1", "swap": "-0.5",
        "net": "10.5", "balance_after": "10010.5", "currency": "USD",
    },
    {
        "deal_id": "2026123457", "position_id": "32146",
        "closed_utc": "2026-11-10T11:01:00.0000000Z",
        "symbol": "XAUUSD", "label": "MojTrade-OMEGA-X-DEMO", "side": "sell",
        "lots": "0.02", "gross": "-7", "commission": "-1", "swap": "-0.2",
        "net": "-8.2", "balance_after": "10002.3", "currency": "USD",
    },
]


@pytest.fixture
def demo_statement_files(tmp_path, settings):
    call_command("seed_online_income_agents", stdout=StringIO())
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    settings.MOJTRADE_PRIVATE_DIR = str(directory)
    log_path = directory / "demo-audit.log"
    records = [
        "MOJTRADE_AUDIT_V1|START|session=" + SESSION +
        "|alias=LITE_DEMO_1|currency=USD|symbol=XAUUSD|mode=demo|count=2",
    ]
    for row in DEALS:
        names = ("deal_id", "position_id", "closed_utc", "side", "lots",
                 "gross", "commission", "swap", "net", "balance_after")
        records.append(
            "MOJTRADE_AUDIT_V1|DEAL|session=" + SESSION
            + "".join("|" + key + "=" + row[key] for key in names)
        )
    records.append(
        "MOJTRADE_AUDIT_V1|END|session=" + SESSION +
        "|count=2|wins=1|gross=5|commission=-2|swap=-0.7|net=2.3"
        "|demo_only=true|external_broker_reconciliation=false"
    )
    log_path.write_text("\n".join(records) + "\n", encoding="utf-8")
    statement = directory / "ctrader-statement-normalized.csv"
    with statement.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in DEALS:
            writer.writerow(row)
    manifest = directory / "ctrader-statement-manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "broker": "LiteFinance", "account_mode": "demo",
        "account_alias": "LITE_DEMO_1", "account_currency": "USD",
        "symbol": "XAUUSD", "source": "ctrader_history_statement_export",
        "full_label_history": True,
        "statement_sha256": hashlib.sha256(statement.read_bytes()).hexdigest(),
        "exported_at_utc": "2026-11-11T12:00:00Z",
    }), encoding="utf-8")
    for file in (log_path, statement, manifest):
        os.chmod(file, 0o600)
    return directory, log_path, statement, manifest


@pytest.mark.django_db
def test_canonical_two_source_matched_receipt_is_not_income(demo_statement_files):
    output = StringIO()
    call_command("mojtrade_statement_crosscheck_cycle", stdout=output)
    assert "new_receipt=1" in output.getvalue()
    assert "real_revenue_verified=false" in output.getvalue()
    task = AgentTask.objects.get(
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        input_data__source_kind="ctrader_demo_statement_crosscheck",
    )
    assert task.agent.code == BOT_CODE
    assert task.status == "completed" and task.cost == 0
    assert task.output_data["verified_effect"] is True
    assert task.output_data["two_unverified_exports_structurally_matched"] is True
    assert task.output_data["statement_crosscheck"]["matched_closing_deals"] == 2
    assert task.output_data["statement_crosscheck"]["real_income_verified"] is False
    assert task.output_data["broker_statement_reconciled"] is False
    assert task.output_data["profit_verified"] is False
    assert task.output_data["orders"] == 0
    assert not Agent.objects.filter(code__startswith="mojtrade").exists()
    assert AuditLog.objects.filter(
        action="mojtrade_demo_two_source_statement_crosschecked",
        target_id=str(task.pk),
    ).count() == 1


@pytest.mark.django_db
def test_same_statement_extracted_twice_does_not_add_demo_profits(demo_statement_files):
    first, created = ingest_demo_statement_crosscheck()
    second, again = ingest_demo_statement_crosscheck()
    assert created and not again and first.pk == second.pk
    assert AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).count() == 1
    assert AuditLog.objects.filter(
        action="mojtrade_demo_two_source_statement_crosschecked",
    ).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("tamper", ["missing_statement", "public_manifest", "wrong_hash", "bad_net", "symlink", "wrong_alias"])
def test_bad_statement_never_creates_receipt(demo_statement_files, tamper):
    _, log, statement, manifest = demo_statement_files
    if tamper == "missing_statement":
        statement.unlink()
    elif tamper == "public_manifest":
        os.chmod(manifest, 0o644)
    elif tamper == "wrong_hash":
        statement.write_bytes(statement.read_bytes() + b"\n")
    elif tamper == "bad_net":
        raw = statement.read_text()
        statement.write_text(raw.replace("-8.2", "-888.2"))
        details = json.loads(manifest.read_text())
        details["statement_sha256"] = hashlib.sha256(statement.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(details))
    elif tamper == "symlink":
        original = statement.with_name("original-statement.csv")
        statement.rename(original)
        statement.symlink_to(original)
    else:
        details = json.loads(manifest.read_text())
        details["account_alias"] = "NOT_THE_ACCOUNT"
        manifest.write_text(json.dumps(details))
    with pytest.raises(DemoStatementBridgeError):
        ingest_demo_statement_crosscheck()
    assert not AgentTask.objects.filter(capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY).exists()


@pytest.mark.django_db
def test_inactive_canonical_bot_cannot_record_valid_statement(demo_statement_files):
    Agent.objects.filter(code=BOT_CODE).update(active=False)
    with pytest.raises(DemoStatementBridgeError, match="canonical_bot_not_active"):
        ingest_demo_statement_crosscheck()


@pytest.mark.django_db
def test_blocked_duplicate_requires_reconciliation(demo_statement_files):
    task, _ = ingest_demo_statement_crosscheck()
    task.status = "blocked"
    task.save(update_fields=["status"])
    with pytest.raises(DemoStatementBridgeError, match="requires_reconciliation"):
        ingest_demo_statement_crosscheck()



@pytest.mark.django_db
def test_two_demo_sources_must_pair_to_same_canonical_log_for_readiness(demo_statement_files):
    before = trading_readiness_report()
    assert before["gates"]["local_demo_closed_deal_log_audited"] is False
    assert before["gates"]["local_two_unverified_demo_exports_matched_to_same_log"] is False
    log_task, _ = ingest_private_demo_evidence()
    log_only = trading_readiness_report()
    assert log_only["demo_log_task_id"] == log_task.pk
    assert log_only["gates"]["local_demo_closed_deal_log_audited"] is True
    assert log_only["gates"]["local_two_unverified_demo_exports_matched_to_same_log"] is False

    statement_task, _ = ingest_demo_statement_crosscheck()
    matched = trading_readiness_report()
    assert matched["statement_task_id"] == statement_task.pk
    assert matched["gates"]["local_two_unverified_demo_exports_matched_to_same_log"] is True
    assert matched["gates"]["broker_authenticated_demo_execution_and_account"] is False
    assert matched["gates"]["canonical_approved_demo_order_control"] is False
    assert matched["gates"]["settled_real_revenue_verified"] is False
    assert matched["operational_completion_percent"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("tamper", [
    "mismatched_demo_digest", "fake_statement_profit", "missing_demo_receipt",
    "changed_source_alias", "unfinished_statement",
])
def test_demo_readiness_never_infers_independent_broker_validation(
    demo_statement_files, tamper,
):
    log_task, _ = ingest_private_demo_evidence()
    statement_task, _ = ingest_demo_statement_crosscheck()
    if tamper == "mismatched_demo_digest":
        values = dict(log_task.input_data)
        values["source_sha256"] = "d" * 64
        log_task.input_data = values
        log_task.save(update_fields=["input_data"])
    elif tamper == "fake_statement_profit":
        values = dict(statement_task.output_data)
        values["profit_verified"] = True
        statement_task.output_data = values
        statement_task.save(update_fields=["output_data"])
    elif tamper == "missing_demo_receipt":
        AuditLog.objects.filter(
            action="mojtrade_demo_closed_deals_audited", target_id=str(log_task.pk),
        ).delete()
    elif tamper == "changed_source_alias":
        values = dict(statement_task.input_data)
        values["account_alias"] = "OTHER_ACCOUNT"
        statement_task.input_data = values
        statement_task.save(update_fields=["input_data"])
    else:
        statement_task.status = "blocked"
        statement_task.save(update_fields=["status"])
    report = trading_readiness_report()
    assert report["gates"]["local_two_unverified_demo_exports_matched_to_same_log"] is False
    assert report["gates"]["broker_authenticated_demo_execution_and_account"] is False
    assert report["gates"]["canonical_approved_demo_order_control"] is False
    assert report["real_revenue_verified"] is False
