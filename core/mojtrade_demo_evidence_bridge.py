"""Canonical Mojtaba.bot.ai ingestion of private cTrader demo-only fill receipts.

No broker network, account access, funds, orders or publication. The claim
"verified_effect" proves only that the DB ledger entry was created, not profit.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat

from django.conf import settings
from django.db import transaction

from core.models import Agent, AgentTask, AuditLog
from core.task_runtime import TaskRuntime
from core.unified_bot_identity import BOT_CODE, MOJTRADE_DEMO_AUDIT_CAPABILITY
from trading.mojtrade_demo_receipt_reconcile import (
    DemoAuditError, MAX_BYTES, reconcile_text,
)


SOURCE_FILENAME = "demo-audit.log"


class DemoEvidenceBridgeError(ValueError):
    """Fail closed if the local receipt or canonical runtime is untrusted."""


def private_demo_evidence() -> tuple[str, dict]:
    root_string = getattr(settings, "MOJTRADE_PRIVATE_DIR", None)
    if not isinstance(root_string, str) or not root_string.startswith("/"):
        raise DemoEvidenceBridgeError("private_demo_evidence_directory_not_configured")
    root = Path(root_string)
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise DemoEvidenceBridgeError("private_demo_evidence_symlink_path")
    if not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise DemoEvidenceBridgeError("private_demo_evidence_directory_insecure")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(root / SOURCE_FILENAME, flags), "rb") as handle:
            before = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_BYTES
                or stat.S_IMODE(before.st_mode) & 0o077
            ):
                raise DemoEvidenceBridgeError("private_demo_evidence_file_insecure")
            raw = handle.read(MAX_BYTES + 1)
            after = os.fstat(handle.fileno())
            if (
                len(raw) != before.st_size
                or len(raw) > MAX_BYTES
                or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            ):
                raise DemoEvidenceBridgeError("private_demo_evidence_modified_during_read")
    except OSError as exc:
        raise DemoEvidenceBridgeError("private_demo_evidence_unavailable") from exc
    try:
        report = reconcile_text(raw.decode("utf-8"))
    except (DemoAuditError, UnicodeError) as exc:
        raise DemoEvidenceBridgeError("private_demo_evidence_schema_or_totals_invalid") from exc
    sha = hashlib.sha256(raw).hexdigest()
    report["source_log_sha256"] = sha
    return sha, report


@transaction.atomic
def ingest_private_demo_evidence() -> tuple[AgentTask, bool]:
    sha, report = private_demo_evidence()
    owner = Agent.objects.select_for_update().filter(code=BOT_CODE, active=True).first()
    if owner is None:
        raise DemoEvidenceBridgeError("canonical_bot_not_active")
    if not owner.capabilities.filter(
        code=MOJTRADE_DEMO_AUDIT_CAPABILITY, active=True, risk_level="low",
    ).exists():
        raise DemoEvidenceBridgeError("canonical_demo_evidence_capability_not_seeded")
    previous = AgentTask.objects.filter(
        agent=owner,
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        input_data__source_sha256=sha,
    ).order_by("pk").first()
    if previous is not None:
        if previous.status != "completed":
            raise DemoEvidenceBridgeError("duplicate_demo_evidence_needs_reconciliation")
        return previous, False

    task = AgentTask.objects.create(
        agent=owner,
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        risk_snapshot="low",
        max_attempts=1,
        status="queued",
        input_data={
            "source_sha256": sha,
            "source_kind": "ctrader_demo_audit_log",
            "demo_only": True,
            "account_alias": report["alias"],
            "symbol": report["symbol"],
        },
    )
    claimed = TaskRuntime().claim(task.pk)
    output = {
        "verified_effect": True,  # Only a persisted private task/receipt.
        "action_performed": "canonical_ctrader_demo_deal_evidence_ingested",
        "evidence": {"source_sha256": sha},
        "demo_trading_history": report,
        "source_log_is_independently_authenticated": False,
        "broker_statement_reconciled": False,
        "revenue_verified": False,
        "profit_verified": False,
        "demo_receipts_not_additive_between_snapshots": True,
        "orders": 0,
        "broker_order_placement_enabled": False,
        "paid_cost": False,
    }
    completed = TaskRuntime().complete(
        task.pk, output_data=output, cost=0, execution_id=claimed.execution_id,
    )
    AuditLog.objects.create(
        actor_type="agent", actor_id=str(owner.pk),
        action="mojtrade_demo_closed_deals_audited",
        target_type="AgentTask", target_id=str(task.pk),
        after_state={
            "source_sha256": sha,
            "demo_trades": report["closing_deal_count"],
            "currency": report["account_currency"],
            "account_alias": report["alias"],
            "broker_reconciled": False,
            "verified_revenue": False,
            "orders": 0,
        },
        trace_id=f"mojtrade-demo-receipts-{task.pk}-{claimed.execution_id}",
    )
    return completed, True
