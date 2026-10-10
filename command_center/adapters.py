"""Read-only aggregate counters from existing Django records."""
from django.utils import timezone
from core.models import Agent, AgentTask, ApprovalRequest

def snapshot():
    return {
        "captured_at": timezone.now().isoformat(),
        "source": "core database",
        "agents": {
            "total": Agent.objects.count(),
            "enabled": Agent.objects.filter(active=True).count(),
        },
        "tasks": {
            "total": AgentTask.objects.count(),
            "queued": AgentTask.objects.filter(status="queued").count(),
            "running": AgentTask.objects.filter(status="running").count(),
        },
        "approvals": {"pending": ApprovalRequest.objects.filter(status="pending").count()},
        "runtime_health": "unknown",
    }
