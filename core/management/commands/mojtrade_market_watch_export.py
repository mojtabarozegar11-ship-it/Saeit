"""Export one fresh Mojtaba.bot.ai market-watch feed into an existing private dir.

No network, public publication, outgoing signal messages, orders or paid calls.
An expired or changed canonical task causes a hard failure, never fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import AgentTask, AuditLog
from core.mojtrade_signal_drafts import (
    MarketWatchDraftError, build_market_watch_drafts,
)
from core.unified_bot_identity import BOT_CODE, MOJTRADE_RESEARCH_CAPABILITY


PRIVATE_NAME = "market-watch-private.json"


def fresh_canonical_drafts(now=None):
    now = now or timezone.now()
    task = (
        AgentTask.objects.filter(
            agent__code=BOT_CODE, agent__active=True,
            action_type=MOJTRADE_RESEARCH_CAPABILITY,
            capability_code=MOJTRADE_RESEARCH_CAPABILITY,
        )
        .order_by("-created_at", "-pk")
        .first()
    )
    if task is None or task.status != "completed":
        raise MarketWatchDraftError("no_completed_canonical_research_receipt")
    output, inputs = task.output_data, task.input_data
    if (not isinstance(output, dict) or not isinstance(inputs, dict)
            or output.get("execution") != "disabled"
            or output.get("orders") != 0
            or output.get("broker_connected") is not False
            or output.get("published") is not False
            or output.get("revenue_verified") is not False):
        raise MarketWatchDraftError("canonical_receipt_not_private_research")
    # A completed task alone does not prove the private research ingest
    # actually passed the canonical audited handoff. Bind the displayed
    # snapshot to its own immutable-semantics audit trail and source hash.
    # This is a local DB-integrity gate, NOT broker-origin authentication.
    source_sha = inputs.get("source_sha256")
    receipts = AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(task.pk),
        action="mojtrade_private_research_ingested",
        actor_type="agent", actor_id=str(task.agent_id),
    )
    if receipts.count() != 1:
        raise MarketWatchDraftError("canonical_research_audit_receipt_missing_or_duplicated")
    attested = receipts.first().after_state
    if (not isinstance(attested, dict)
            or attested.get("source_sha256") != source_sha
            or attested.get("observed_signals") != 2
            or attested.get("research_only") is not True
            or attested.get("execution") != "disabled"
            or attested.get("orders") != 0
            or not isinstance(output.get("evidence"), dict)
            or output["evidence"].get("source_sha256") != source_sha):
        raise MarketWatchDraftError("canonical_research_audit_digest_mismatch")
    report = {
        "execution": "disabled",
        "orders": 0,
        "action": "research_only",
        "observation_generated_at": inputs.get("observation_generated_at"),
        "observation_expires_at": output.get("observation_expires_at"),
        "signals": output.get("market_observations"),
    }
    fresh = build_market_watch_drafts(
        report, output.get("strategy_risk_review"),
        inputs.get("source_sha256"), now=now,
    )
    if fresh != output.get("market_watch_drafts"):
        raise MarketWatchDraftError("stored_draft_differs_from_validated_receipt")
    return task.pk, fresh


def write_private_feed(root: Path, document: dict) -> None:
    if (not root.is_absolute() or any(folder.is_symlink() for folder in
                                      (root, *root.parents))
            or not root.is_dir()
            or stat.S_IMODE(root.stat().st_mode) & 0o077):
        raise MarketWatchDraftError("private_dir_not_verified_0700")
    target = root / PRIVATE_NAME
    if target.is_symlink() or (
        target.exists() and (
            not target.is_file()
            or stat.S_IMODE(target.stat().st_mode) & 0o077
        )
    ):
        raise MarketWatchDraftError("existing_private_feed_is_unsafe")
    payload = (
        json.dumps(document, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=root, prefix=".mojtrade-watch-", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Command(BaseCommand):
    help = (
        "Write one fresh, nonexecutable FA/EN/AR market-watch draft to an "
        "existing mode-0700 private directory; no public signal publication."
    )

    def handle(self, *args, **options):
        try:
            configured = getattr(settings, "MOJTRADE_PRIVATE_DIR", None)
            if not isinstance(configured, str) or not configured.startswith("/"):
                raise MarketWatchDraftError("mojtrade_private_dir_not_configured")
            task_id, document = fresh_canonical_drafts()
            write_private_feed(Path(configured), document)
        except (OSError, ValueError, TypeError) as exc:
            raise CommandError(
                "MOJTRADE_PRIVATE_WATCH_EXPORT_REJECTED: " + str(exc)
            ) from exc
        self.stdout.write(self.style.SUCCESS(
            f"MOJTRADE_PRIVATE_WATCH_EXPORTED task={task_id} "
            "owner=mojtaba-bot-ai languages=fa,en,ar "
            "publications=0 orders=0 broker_connected=false "
            "revenue_not_verified=true"
        ))
