"""Retire explicitly identified legacy agent identities without losing history.

This is intentionally not an automatic 'delete every agent with zero sales'
command: operational agents can protect a site without directly earning money.
The known legacy roles below have been superseded by the central economic master
under the canonical Mojtaba.bot.ai owner. External scheduler changes need live evidence review.
"""

import json
import uuid
from contextlib import nullcontext
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Agent, AgentTask, AuditLog, ApprovalGrant
from core.knowledge_agent_models import KnowledgeAgentRun
from core.approval import ApprovalService
from core.unified_bot_identity import BOT_CODE


LEGACY_AGENT_CODES = frozenset({
    "core_research",
    "newsletter-specialist",
    "newsletter-company-news",
    "newsletter-world-watch",
    "newsletter-unit-reports",
    # Former independent content/specialist Agent identities. Retire only
    # after exact-module handoff; their program logic remains in the one bot.
    "content-director",
    "content-research",
    "knowledge-content-director",
    "company-activity-intelligence",
})
# The prefix alone cannot prove redundancy. Some older income agents may run
# external integrations that are not represented by Django AgentTask rows.
LEGACY_SUCCESSORS = {
    "core_research": BOT_CODE,
    "newsletter-specialist": BOT_CODE,
    "newsletter-company-news": BOT_CODE,
    "newsletter-world-watch": BOT_CODE,
    "newsletter-unit-reports": BOT_CODE,
    "content-director": BOT_CODE,
    "content-research": BOT_CODE,
    "knowledge-content-director": BOT_CODE,
    "company-activity-intelligence": BOT_CODE,
}
REVIEW_ONLY_PREFIXES = ("income-",)
PROTECTED_AGENT_CODES = frozenset({
    BOT_CODE,
    "economic-master-agent",
    "moj_1ro_1",
    # Content and knowledge specialist identities are no longer permanently
    # protected from merger. Their dependency and successor-proof gates
    # apply in assess_agent(), and every write still needs an exact owner grant.
})
# A successor is not proven merely because its Agent row is active.
# Each retiring newsletter role needs recent receipts for its own content type.
# Core research has no independently accepted successor receipt contract yet.
SUCCESSOR_STORY_COVERAGE = {
    "newsletter-specialist": ("company", "world", "report"),
    "newsletter-company-news": ("company",),
    "newsletter-world-watch": ("world",),
    "newsletter-unit-reports": ("report",),
    "content-director": ("company",),
    "content-research": ("report",),
    "company-activity-intelligence": ("company",),
}
SUCCESSOR_PROOF_STATUSES = ("published",)
ACTIVE_TASK_STATUSES = ("queued", "running", "blocked")
PENDING_NEWSLETTER_STATUSES = ("draft", "approved", "scheduled", "review", "queued", "processing")


def is_known_legacy(code):
    return code in LEGACY_AGENT_CODES


def assess_agent(agent):
    """Conservative classification using the *current* database, not a vanity score."""
    task_qs = AgentTask.objects.filter(agent=agent)
    active_tasks = task_qs.filter(status__in=ACTIVE_TASK_STATUSES).count()
    review_cutoff = timezone.now() - timedelta(days=30)
    recent_completed = task_qs.filter(
        status="completed", updated_at__gte=review_cutoff
    ).count()
    pending_stories = agent.newsletter_stories.filter(
        status__in=PENDING_NEWSLETTER_STATUSES
    ).count()
    pending_distributions = agent.newsletter_stories.filter(
        publications__status__in=("queued", "blocked")
    ).distinct().count()
    recent_publications = agent.newsletter_stories.filter(
        status="published", published_at__gte=review_cutoff
    ).count()
    # A live, exclusively held capability might still be called by a scheduler
    # or external system even if Django has no recent AgentTask record.
    unique_active_capabilities = [
        cap.code for cap in agent.capabilities.filter(active=True)
        if not cap.agents.filter(active=True).exclude(pk=agent.pk).exists()
    ]
    protected = agent.code in PROTECTED_AGENT_CODES
    legacy = is_known_legacy(agent.code)
    replacement_code = LEGACY_SUCCESSORS.get(agent.code)
    successor = Agent.objects.filter(
        code=replacement_code, active=True
    ).first() if replacement_code else None
    required_story_types = SUCCESSOR_STORY_COVERAGE.get(agent.code, ())
    covered_story_types = tuple(
        story_type for story_type in required_story_types
        if successor is not None and successor.newsletter_stories.filter(
            story_type=story_type,
            created_at__gte=review_cutoff,
            status__in=SUCCESSOR_PROOF_STATUSES,
            published_at__isnull=False,
            manager_action__startswith="NEWSROOM_QUALITY=",
        ).exists()
    )
    missing_successor_coverage = [
        story_type for story_type in required_story_types
        if story_type not in covered_story_types
    ]
    if agent.code == "core_research":
        # Keep exclusive research identity until a separately verified output
        # contract is implemented; a completed task alone is insufficient.
        missing_successor_coverage.append("accepted_research_delivery")
    if agent.code == "knowledge-content-director":
        # Knowledge is not a NewsletterStory. Require a genuinely completed
        # canonical generation task paired to the same completed run and
        # nonempty reviewed book. An Agent row or generated task alone is NOT
        # successor proof. The live handoff receipt is separately mandatory.
        verified_knowledge_output = False
        if successor is not None:
            for completed in AgentTask.objects.filter(
                agent=successor,
                action_type="knowledge_content_generation",
                capability_code="research-write-review",
                status="completed",
                updated_at__gte=review_cutoff,
            ).order_by("-updated_at", "-pk")[:100]:
                output = completed.output_data
                if not isinstance(output, dict):
                    continue
                run_id = output.get("run_id")
                book_id = output.get("book_id")
                if type(run_id) is not int or type(book_id) is not int:
                    continue
                if KnowledgeAgentRun.objects.filter(
                    pk=run_id, book_id=book_id,
                    status="completed",
                    finished_at__gte=review_cutoff,
                    book__generated_sections__gt=0,
                ).exclude(book__content="").exists():
                    verified_knowledge_output = True
                    break
        if not verified_knowledge_output:
            missing_successor_coverage.append("accepted_knowledge_delivery")

    if protected:
        decision = "retain_required"
    elif active_tasks or pending_stories or pending_distributions:
        decision = "hold_for_dependency"
    elif not agent.active:
        decision = "already_retired"
    elif recent_completed or recent_publications:
        decision = "review_recent_outputs"
    elif unique_active_capabilities:
        decision = "review_unique_capability"
    elif not legacy:
        decision = "review_live_outcomes"
    elif replacement_code and successor is None:
        decision = "hold_missing_successor"
    elif missing_successor_coverage:
        decision = "hold_unproven_successor_coverage"
    else:
        decision = "retire_safe"

    return {
        "code": agent.code,
        "active": agent.active,
        "decision": decision,
        "active_tasks": active_tasks,
        "recent_completed_tasks": recent_completed,
        "recent_publications": recent_publications,
        "historical_tasks": task_qs.count(),
        "pending_stories": pending_stories,
        "pending_distributions": pending_distributions,
        "unique_active_capabilities": unique_active_capabilities,
        "review_only_prefix": any(agent.code.startswith(p) for p in REVIEW_ONLY_PREFIXES),
        "replacement_agent": replacement_code,
        "missing_successor_coverage": missing_successor_coverage,
        "financial_outcome": "not_assessed_from_task_counts",
        "retirement_readiness_scope": "source_only_not_live_verified",
        "deactivation_authorized_by_preview": False,
    }


HANDOFF_EVIDENCE_FIELDS = (
    "canonical_successor_runtime_verified",
    "external_legacy_schedulers_stopped",
    "all_pending_tasks_reconciled",
    "historical_data_preserved",
    "rollback_ready",
)


def require_verified_handoff(agent):
    """Require a recent, traceable live handoff receipt, not a Django-only score.

    This check is a *necessary* internal gate, not independent proof that the
    supplied attestation actually observed the VPS/cPanel live processes.
    """
    cutoff = timezone.now() - timedelta(days=1)
    receipt = AuditLog.objects.filter(
        action="single_bot_live_handoff_verified",
        target_type="Agent",
        target_id=str(agent.pk),
        created_at__gte=cutoff,
    ).order_by("-created_at", "-pk").first()
    values = receipt.after_state if receipt is not None else {}
    if (
        not isinstance(values, dict)
        or values.get("legacy_code") != agent.code
        or values.get("canonical_bot_code") != BOT_CODE
        or any(values.get(field) is not True for field in HANDOFF_EVIDENCE_FIELDS)
        or not isinstance(values.get("live_inventory_receipt_id"), str)
        or not values["live_inventory_receipt_id"].strip()
        or not isinstance(values.get("canonical_successor_receipt_id"), str)
        or not values["canonical_successor_receipt_id"].strip()
    ):
        raise CommandError("LEGACY_RETIRE_LIVE_HANDOFF_RECEIPT_REQUIRED")
    return receipt


def authorize_single_agent_retirement(agent, *, grant_id, receipt):
    """Consume a one-off exact-agent grant atomically with retirement."""
    grant = ApprovalGrant.objects.select_for_update().select_related(
        "approval"
    ).filter(pk=grant_id).first()
    if (
        grant is None
        or grant.actor_id != grant.approval.requested_by_id
        or grant.approval.status != "approved"
        or grant.approval.action_type != "retire_legacy_agent"
        or grant.approval.target_type != "Agent"
        or grant.approval.target_id != str(agent.pk)
    ):
        raise CommandError("LEGACY_RETIRE_EXACT_OWNER_APPROVAL_REQUIRED")
    scope = {
        "action": "retire_legacy_agent",
        "agent_code": agent.code,
        "canonical_bot_code": BOT_CODE,
        "live_handoff_receipt": receipt.trace_id,
    }
    try:
        ApprovalService().authorize_grant(grant_id, scope)
    except ValueError as exc:
        raise CommandError("LEGACY_RETIRE_APPROVAL_GRANT_REJECTED") from exc


class Command(BaseCommand):
    help = (
        "Inventory agents; optionally retire only known legacy identities with "
        "no active tasks or pending stories, preserving historical rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Deactivate one approved, live-verified legacy identity only",
        )
        parser.add_argument("--agent-code", type=str, default=None)
        parser.add_argument("--approval-grant-id", type=int, default=None)

    def handle(self, *args, **options):
        rows = []
        applying = bool(options["apply"])
        target_code = options.get("agent_code")
        grant_id = options.get("approval_grant_id")
        if target_code is not None and target_code not in LEGACY_AGENT_CODES:
            raise CommandError("LEGACY_RETIRE_UNKNOWN_OR_PROTECTED_AGENT")
        if applying and (
            target_code not in LEGACY_AGENT_CODES
            or type(grant_id) is not int or grant_id <= 0
        ):
            raise CommandError("LEGACY_RETIRE_EXACT_AGENT_AND_GRANT_REQUIRED")
        if not applying and grant_id is not None:
            raise CommandError("LEGACY_RETIRE_GRANT_ONLY_ALLOWED_WITH_APPLY")
        # Inventory mode must neither lock agent rows nor start a write
        # transaction: it can run while production workers are dispatching.
        with transaction.atomic() if applying else nullcontext():
            agents = (
                Agent.objects.select_for_update().filter(code=target_code).order_by("code")
                if applying else Agent.objects.order_by("code")
            )
            for agent in agents:
                row = assess_agent(agent)
                if applying:
                    if row["decision"] != "retire_safe":
                        raise CommandError(
                            "LEGACY_RETIRE_NOT_SAFE_SOURCE_CANDIDATE: " + row["decision"]
                        )
                    receipt = require_verified_handoff(agent)
                    authorize_single_agent_retirement(
                        agent, grant_id=grant_id, receipt=receipt
                    )
                    agent.active = False
                    agent.save(update_fields=["active", "updated_at"])
                    AuditLog.objects.create(
                        actor_type="system",
                        actor_id="agent-consolidation",
                        action="legacy_agent_retired",
                        target_type="Agent",
                        target_id=str(agent.pk),
                        before_state={"code": agent.code, "active": True},
                        after_state={
                            "code": agent.code,
                            "active": False,
                            "reason": "legacy_role_without_active_tasks_or_pending_stories",
                            "history_preserved": True,
                            "canonical_bot_code": BOT_CODE,
                            "live_handoff_trace_id": receipt.trace_id,
                            "owner_approval_grant_id": grant_id,
                        },
                        trace_id=f"agent-retire-{agent.pk}-{uuid.uuid4().hex[:12]}",
                    )
                    row["decision"] = "retired"
                    row["active"] = False
                rows.append(row)
            if applying and len(rows) != 1:
                raise CommandError("LEGACY_RETIRE_EXACT_AGENT_NOT_FOUND")

        self.stdout.write(json.dumps({
            "mode": "apply" if options["apply"] else "preview",
            "agents": rows,
            "summary": {
                "total": len(rows),
                "retired_now": sum(r["decision"] == "retired" for r in rows),
                "source_only_retirement_candidates": sum(r["decision"] == "retire_safe" for r in rows),
                "ready_to_retire": 0 if not applying else sum(r["decision"] == "retired" for r in rows),
                "held_for_dependency": sum(r["decision"] == "hold_for_dependency" for r in rows),
                "missing_successor": sum(r["decision"] == "hold_missing_successor" for r in rows),
                "unproven_successor_coverage": sum(r["decision"] == "hold_unproven_successor_coverage" for r in rows),
                "unknown_requires_live_review": sum(r["decision"] == "review_live_outcomes" for r in rows),
                "recent_output_requires_review": sum(r["decision"] == "review_recent_outputs" for r in rows),
                "unique_capability_requires_review": sum(r["decision"] == "review_unique_capability" for r in rows),
            },
        }, ensure_ascii=False, default=str))
