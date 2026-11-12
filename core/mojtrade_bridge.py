"""Offline MojTrade research ingestion owned by the one canonical bot.

This boundary has no broker API, trading credentials, order instructions,
network fetches, public publication, or monetary side effects. It consumes
one private previously-observed file and records a single audited AgentTask.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.db import transaction

from core.models import Agent, AgentTask, AuditLog
from core.task_runtime import TaskRuntime
from core.unified_bot_identity import BOT_CODE, MOJTRADE_RESEARCH_CAPABILITY
from scripts.mojtrade_consume_observation import (
    ObservationError, validate_observation_payload,
)


SOURCE_NAME = "validated-payload.json"
MAX_SOURCE_BYTES = 96_000
EXPECTED_METHOD = "sma20-sma50-momentum10-v1-closed-1h"


class MojTradeBridgeError(ValueError):
    """The research-only bridge refuses to consume a source or dispatch work."""


def private_snapshot(now: datetime | None = None) -> tuple[str, dict]:
    """Read exactly one allowlisted, private, non-symlink regular file."""
    configured = getattr(settings, "MOJTRADE_PRIVATE_DIR", None)
    if not isinstance(configured, str) or not configured.startswith("/"):
        raise MojTradeBridgeError("mojtrade_private_dir_not_configured")
    root = Path(configured)
    if any(folder.is_symlink() for folder in (root, *root.parents)):
        raise MojTradeBridgeError("mojtrade_private_path_symlink_rejected")
    if not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise MojTradeBridgeError("mojtrade_private_dir_must_be_0700")
    source = root / SOURCE_NAME
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        with os.fdopen(os.open(source, flags), "rb") as handle:
            before = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or not 0 < before.st_size <= MAX_SOURCE_BYTES
                or stat.S_IMODE(before.st_mode) & 0o077
            ):
                raise MojTradeBridgeError("mojtrade_private_observation_unsafe")
            raw = handle.read(MAX_SOURCE_BYTES + 1)
            after = os.fstat(handle.fileno())
            if (
                len(raw) != before.st_size
                or len(raw) > MAX_SOURCE_BYTES
                or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
            ):
                raise MojTradeBridgeError("mojtrade_private_observation_changed")
    except OSError as exc:
        raise MojTradeBridgeError("mojtrade_private_observation_unavailable") from exc
    try:
        report = validate_observation_payload(json.loads(raw.decode("utf-8")), now=now)
        generated = datetime.fromisoformat(report["observation_generated_at"])
        for signal in report["signals"]:
            observed = datetime.fromisoformat(signal["observed_at"])
            if (
                not re.fullmatch(r"[0-9a-f]{24}", signal["id"])
                or signal["method"] != EXPECTED_METHOD
                or not generated - timedelta(hours=3) <= observed <= generated
            ):
                raise MojTradeBridgeError("mojtrade_signal_integrity_rejected")
    except (UnicodeError, json.JSONDecodeError, ObservationError) as exc:
        raise MojTradeBridgeError("mojtrade_observation_validation_failed") from exc
    if report.get("execution") != "disabled" or report.get("orders") != 0:
        raise MojTradeBridgeError("mojtrade_execution_must_remain_disabled")
    return hashlib.sha256(raw).hexdigest(), report


@transaction.atomic
def ingest_private_observation(now: datetime | None = None) -> tuple[AgentTask, bool]:
    """Idempotent, database-audited research receipt under the canonical owner.

    Locks the canonical Agent row before checking duplicates/claiming work.
    No independent MojTrade Agent is created. Any failure rolls back the task
    and its audit records. Do not confuse this with trading or profit.
    """
    source_sha, report = private_snapshot(now=now)
    owner = Agent.objects.select_for_update().filter(code=BOT_CODE, active=True).first()
    if not owner:
        raise MojTradeBridgeError("canonical_bot_is_not_active")
    capability = owner.capabilities.filter(
        code=MOJTRADE_RESEARCH_CAPABILITY, active=True,
        risk_level="low",
    ).first()
    if capability is None:
        raise MojTradeBridgeError("canonical_mojtrade_research_capability_missing")

    existing = AgentTask.objects.filter(
        agent=owner,
        action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        input_data__source_sha256=source_sha,
    ).order_by("pk").first()
    if existing:
        if existing.status != "completed":
            raise MojTradeBridgeError("existing_snapshot_task_requires_reconciliation")
        return existing, False

    task = AgentTask.objects.create(
        agent=owner,
        action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        risk_snapshot="low",
        max_attempts=1,
        status="queued",
        input_data={
            "source_sha256": source_sha,
            "observation_generated_at": report["observation_generated_at"],
            "source": "mojtrade-vps",
            "action": "research_only",
        },
    )
    execution = TaskRuntime().claim(task.pk)
    output = {
        "verified_effect": True,  # Private research receipt in the database ONLY.
        "action_performed": "canonical_private_market_observation_ingested",
        "evidence": {"source_sha256": source_sha},
        "market_observations": report["signals"],
        "report_type": report["report_type"],
        "execution": "disabled",
        "orders": 0,
        "broker_connected": False,
        "published": False,
        "revenue_verified": False,
        "profit_verified": False,
    }
    completed = TaskRuntime().complete(
        task.pk, output_data=output, cost=0, execution_id=execution.execution_id,
    )
    AuditLog.objects.create(
        actor_type="agent",
        actor_id=str(owner.pk),
        action="mojtrade_private_research_ingested",
        target_type="AgentTask",
        target_id=str(task.pk),
        after_state={
            "source_sha256": source_sha,
            "observed_signals": len(report["signals"]),
            "research_only": True,
            "orders": 0,
            "execution": "disabled",
        },
        trace_id=f"mojtrade-research-{task.pk}-{execution.execution_id}",
    )
    return completed, True
