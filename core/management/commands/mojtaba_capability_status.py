"""Read-only capability ownership and publication gate evidence.

This management command never schedules work, starts an autonomous worker,
publishes, calls weather/news providers, contacts customers, or changes state.
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.canonical_content_owner import CANONICAL_AGENT_CODE
from core.knowledge_agent_models import KnowledgeAgentRun
from core.models import Agent, AgentTask
from core.newsletter_models import NewsletterSchedule, NewsletterStory, NewsletterSubmission



RETIRED_CONTENT_CODES = (
    "content-research",
    "content-director",
    "knowledge-content-director",
    "company-activity-intelligence",
)
NONTERMINAL_TASK_STATES = ("queued", "running", "blocked")


def _bounded_recent_task_health(limit=128):
    """Sample latest tasks by indexed PK; never run an unbounded status scan.

    A quick operational hint, NOT an all-history task census. An old failed
    task outside this window must never be represented as nonexistent.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 128:
        raise ValueError("limit must be between 1 and 128")
    rows = list(AgentTask.objects.order_by("-pk").values_list(
        "status", "updated_at", "cost",
    )[:limit])
    counts = {key: 0 for key in ("queued", "running", "completed", "failed", "cancelled")}
    cutoff = timezone.now() - timedelta(minutes=15)
    stale_running = 0
    sample_cost = Decimal("0")
    for status, updated_at, cost in rows:
        if status in counts:
            counts[status] += 1
        if status == "running" and updated_at and updated_at <= cutoff:
            stale_running += 1
        sample_cost += cost or Decimal("0")
    return {
        **counts,
        "stale_running_over_15_minutes": stale_running,
        "recorded_total_cost_not_verified_revenue": str(sample_cost),
        "sampled_task_rows": len(rows),
        "sample_limit": limit,
        "complete_population_verified": False,
        "metric_scope": "LATEST_PRIMARY_KEY_SAMPLE_NOT_FULL_TASK_COUNTS",
    }


def capability_snapshot():
    """Return evidence from the Django database only; not a live host attestation."""
    today = timezone.localdate()
    canonical_active = Agent.objects.filter(
        code=CANONICAL_AGENT_CODE, active=True,
    ).exists()
    active_legacy = list(Agent.objects.filter(
        code__in=RETIRED_CONTENT_CODES, active=True,
    ).order_by("code").values_list("code", flat=True))
    pending_legacy = AgentTask.objects.filter(
        agent__code__in=RETIRED_CONTENT_CODES,
        status__in=NONTERMINAL_TASK_STATES,
    ).count()

    weather_story = NewsletterStory.objects.filter(
        fingerprint=f"weather-iran-{today.isoformat()}",
    ).values("status", "agent__code").first()
    schedule = NewsletterSchedule.objects.filter(active=True).first()
    pending_news = NewsletterSubmission.objects.filter(status="queued").count()
    running_news = NewsletterSubmission.objects.filter(status="processing").count()
    pending_knowledge = KnowledgeAgentRun.objects.filter(status="queued").count()
    task_health = _bounded_recent_task_health()

    blockers = []
    if not canonical_active:
        blockers.append("CANONICAL_OWNER_INACTIVE")
    if active_legacy:
        blockers.append("LEGACY_CONTENT_AGENT_ACTIVE")
    if pending_legacy:
        blockers.append("UNRECONCILED_LEGACY_CONTENT_TASKS")
    if weather_story and weather_story["agent__code"] != CANONICAL_AGENT_CODE:
        blockers.append("WEATHER_OWNED_BY_LEGACY_AGENT")
    if not schedule or schedule.publication_requires_approval:
        blockers.append("EDITORIAL_APPROVAL_REQUIRED")
    if pending_news or running_news:
        blockers.append("NEWSROOM_SUBMISSIONS_PENDING")
    if pending_knowledge:
        blockers.append("KNOWLEDGE_GENERATION_PENDING")
    if task_health["stale_running_over_15_minutes"]:
        blockers.append("STALE_RUNNING_AGENT_TASKS")
    if task_health["failed"]:
        blockers.append("FAILED_AGENT_TASKS_REQUIRE_REVIEW")
    blockers.append("AGENT_TASK_FULL_CENSUS_UNVERIFIED")

    return {
        "scope": "DJANGO_DATABASE_READ_ONLY",
        "as_of_date": today.isoformat(),
        "canonical_agent_code": CANONICAL_AGENT_CODE,
        "canonical_owner_active": canonical_active,
        "active_legacy_content_codes": active_legacy,
        "nonterminal_legacy_content_tasks": pending_legacy,
        "weather_today": weather_story or {"status": "not_recorded"},
        "newsroom": {
            "queued_submissions": pending_news,
            "processing_submissions": running_news,
            "publication_schedule_present": schedule is not None,
            "approval_required": bool(
                schedule is None or schedule.publication_requires_approval
            ),
        },
        "knowledge_queued_runs": pending_knowledge,
        "runtime_tasks": task_health,
        "blockers": blockers,
        "publication_live_verified": False,
        "host_cron_verified": False,
        "payment_and_revenue_verified": False,
        "note": "Task metrics are a bounded recent sample, not full-history counts. Database snapshot is not live delivery, production deployment or revenue proof.",
    }


class Command(BaseCommand):
    help = "Read-only canonical bot capability and safety-gate snapshot (JSON)."

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(capability_snapshot(), ensure_ascii=False, sort_keys=True))
