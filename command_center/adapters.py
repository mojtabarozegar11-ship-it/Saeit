"""Read-only historical Django task evidence. Do not infer external agent health."""
from datetime import timedelta
from django.db.models import Count, Q, Max
from django.utils import timezone
from core.models import Agent, AgentTask, ApprovalRequest


def snapshot():
    now = timezone.now()
    statuses = ("queued", "running", "completed", "failed", "cancelled")
    tasks = {status: AgentTask.objects.filter(status=status).count() for status in statuses}
    tasks["total"] = AgentTask.objects.count()
    tasks["other"] = tasks["total"] - sum(tasks[status] for status in statuses)
    tasks["stale_running"] = AgentTask.objects.filter(
        status="running", updated_at__lte=now - timedelta(minutes=15)
    ).count()
    per_agent = list(Agent.objects.order_by("code").annotate(
        tasks_total=Count("tasks"),
        tasks_completed=Count("tasks", filter=Q(tasks__status="completed")),
        tasks_failed=Count("tasks", filter=Q(tasks__status="failed")),
        tasks_running=Count("tasks", filter=Q(tasks__status="running")),
        last_task_at=Max("tasks__updated_at"),
    ).values("code", "name", "active", "tasks_total", "tasks_completed",
             "tasks_failed", "tasks_running", "last_task_at")[:200])
    for item in per_agent:
        item["last_task_at"] = item["last_task_at"].isoformat() if item["last_task_at"] else None
        item["live_worker_verified"] = False
    return {
        "captured_at": now.isoformat(),
        "source": "Django core database only (not VPS/cPanel heartbeat)",
        "scope": "django_core_records_not_tenant_filtered",
        "agents": {"total": Agent.objects.count(), "enabled": Agent.objects.filter(active=True).count()},
        "tasks": tasks,
        "per_agent": per_agent,
        "per_agent_truncated": Agent.objects.count() > 200,
        "approvals": {"pending": ApprovalRequest.objects.filter(status="pending").count()},
        "runtime_health": "unknown",
        "live_connected": False,
    }
