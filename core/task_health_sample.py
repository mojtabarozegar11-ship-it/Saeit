"""Fast, read-only recent task sample for operator-facing health views.

The `core_agenttask.status` field is not indexed on the audited live
MariaDB instance, making unrestricted status COUNT queries expensive.
Never present sample counts as complete task-population metrics.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from core.models import AgentTask


RECENT_TASK_LIMIT = 128


def bounded_recent_task_health(limit=RECENT_TASK_LIMIT):
    """Read at most 128 newest tasks by indexed PK, with honest sample scope."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= RECENT_TASK_LIMIT:
        raise ValueError("recent task sample limit must be between 1 and 128")

    rows = list(
        AgentTask.objects.order_by("-pk")
        .values_list("status", "updated_at", "cost")[:limit]
    )
    counts = {
        status: 0
        for status in ("queued", "running", "blocked", "completed", "failed", "cancelled")
    }
    stale_running = 0
    sample_cost = Decimal("0")
    cutoff = timezone.now() - timedelta(minutes=15)
    for status, updated_at, cost in rows:
        if status in counts:
            counts[status] += 1
        if status == "running" and updated_at and updated_at <= cutoff:
            stale_running += 1
        sample_cost += cost or Decimal("0")

    nonterminal = sum(
        1 for status, _, _ in rows if status not in ("completed", "failed", "cancelled")
    )
    return {
        **counts,
        "nonterminal": nonterminal,
        "stale_running_over_15_minutes": stale_running,
        "recorded_total_cost_not_verified_revenue": str(sample_cost),
        "sampled_task_rows": len(rows),
        "sample_limit": limit,
        "complete_population_verified": False,
        "metric_scope": "LATEST_PRIMARY_KEY_SAMPLE_NOT_FULL_TASK_COUNTS",
    }
