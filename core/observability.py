from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .models import AgentTask, AuditLog


@dataclass(frozen=True)
class RuntimeMetrics:
    queued: int
    running: int
    completed: int
    failed: int
    cancelled: int
    stale_running: int
    total_cost: object


class RuntimeObservability:
    """Read-only runtime metrics for health, dashboards, and production gates."""

    def snapshot(self, stale_after_seconds=900):
        if (
            isinstance(stale_after_seconds, bool)
            or not isinstance(stale_after_seconds, int)
            or stale_after_seconds <= 0
        ):
            raise ValueError("stale_after_seconds must be a positive integer")

        cutoff = timezone.now() - timedelta(seconds=stale_after_seconds)
        counts = {
            status: AgentTask.objects.filter(status=status).count()
            for status in ("queued", "running", "completed", "failed", "cancelled")
        }
        total_cost = AgentTask.objects.aggregate_total_cost()
        stale_running = AgentTask.objects.filter(
            status="running", updated_at__lte=cutoff
        ).count()

        return RuntimeMetrics(
            queued=counts["queued"],
            running=counts["running"],
            completed=counts["completed"],
            failed=counts["failed"],
            cancelled=counts["cancelled"],
            stale_running=stale_running,
            total_cost=total_cost,
        )

    def audit_count(self, action=None):
        query = AuditLog.objects.all()
        if action:
            query = query.filter(action=action)
        return query.count()
