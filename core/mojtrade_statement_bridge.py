"""Canonical audit of two privately supplied DEMO history exports.

This bridge records that two *unverified source extracts* matched; it does
not authenticate a broker statement, initiate orders or count real revenues.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings
from django.db import transaction

from core.models import Agent, AgentTask, AuditLog
from core.mojtrade_demo_evidence_bridge import (
    DemoEvidenceBridgeError, private_demo_evidence,
)
from core.task_runtime import TaskRuntime
from core.unified_bot_identity import BOT_CODE, MOJTRADE_DEMO_AUDIT_CAPABILITY
from trading.mojtrade_broker_statement_check import (
    StatementCrosscheckError, compare_private_files,
)

STATEMENT_FILENAME = "ctrader-statement-normalized.csv"
MANIFEST_FILENAME = "ctrader-statement-manifest.json"


class DemoStatementBridgeError(ValueError):
    pass


@transaction.atomic
def ingest_demo_statement_crosscheck() -> tuple[AgentTask, bool]:
    """Compare actual existing private files; then register a canonical receipt."""
    log_sha, log = private_demo_evidence()  # Reuses 0700/0600 checks for log/root.
    root = Path(getattr(settings, "MOJTRADE_PRIVATE_DIR"))
    try:
        verdict = compare_private_files(
            root / "demo-audit.log",
            root / STATEMENT_FILENAME,
            root / MANIFEST_FILENAME,
        )
    except StatementCrosscheckError as exc:
        raise DemoStatementBridgeError("demo_statement_pair_invalid_or_unmatched") from exc
    if verdict["log_sha256"] != log_sha or verdict["account_alias"] != log["alias"]:
        raise DemoStatementBridgeError("demo_evidence_source_or_alias_changed")
    if verdict["symbol"] != log["symbol"] or verdict["account_currency"] != log["account_currency"]:
        raise DemoStatementBridgeError("demo_evidence_instrument_or_currency_changed")
    fingerprint = hashlib.sha256((
        "mojtrade-demo-two-extracts-v1|" + verdict["log_sha256"] + "|" +
        verdict["statement_sha256"] + "|" + verdict["statement_manifest_sha256"]
    ).encode("ascii")).hexdigest()

    owner = Agent.objects.select_for_update().filter(code=BOT_CODE, active=True).first()
    if owner is None:
        raise DemoStatementBridgeError("canonical_bot_not_active")
    if not owner.capabilities.filter(
        code=MOJTRADE_DEMO_AUDIT_CAPABILITY, active=True, risk_level="low",
    ).exists():
        raise DemoStatementBridgeError("canonical_demo_audit_capability_not_seeded")
    previous = AgentTask.objects.filter(
        agent=owner,
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        input_data__source_sha256=fingerprint,
    ).order_by("pk").first()
    if previous is not None:
        if previous.status != "completed":
            raise DemoStatementBridgeError("demo_statement_duplicate_requires_reconciliation")
        return previous, False

    task = AgentTask.objects.create(
        agent=owner,
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        risk_snapshot="low",
        max_attempts=1,
        status="queued",
        input_data={
            "source_sha256": fingerprint,
            "source_kind": "ctrader_demo_statement_crosscheck",
            "demo_only": True,
            "account_alias": verdict["account_alias"],
            "symbol": verdict["symbol"],
            "source_log_sha256": log_sha,
            "normalized_statement_sha256": verdict["statement_sha256"],
            "source_manifest_sha256": verdict["statement_manifest_sha256"],
        },
    )
    claimed = TaskRuntime().claim(task.pk)
    output = {
        "verified_effect": True,  # Only durable ledger receipt.
        "action_performed": "canonical_ctrader_demo_statement_crosscheck_recorded",
        "two_unverified_exports_structurally_matched": True,
        "statement_crosscheck": verdict,
        "broker_statement_reconciled": False,
        "realized_revenue_verified": False,
        "profit_verified": False,
        "orders": 0,
        "broker_connected": False,
        "paid_cost": False,
    }
    completed = TaskRuntime().complete(
        task.pk, output_data=output, cost=0, execution_id=claimed.execution_id,
    )
    AuditLog.objects.create(
        actor_type="agent", actor_id=str(owner.pk),
        action="mojtrade_demo_two_source_statement_crosschecked",
        target_type="AgentTask", target_id=str(task.pk),
        after_state={
            "source_sha256": fingerprint,
            "matched_demo_deals": verdict["matched_closing_deals"],
            "account_alias": verdict["account_alias"],
            "currency": verdict["account_currency"],
            "net_demo_only": verdict["statement_net_demo_only"],
            "broker_statement_authenticated": False,
            "real_revenue_verified": False,
            "orders": 0,
        },
        trace_id=f"mojtrade-demo-statement-{task.pk}-{claimed.execution_id}",
    )
    return completed, True
