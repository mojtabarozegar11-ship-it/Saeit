"""Evidence-based read-only task stage aggregation; no inferred completion."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count
from core.models import AgentTask

@staff_member_required
@require_GET
def stages(request):
    rows = list(AgentTask.objects.values("action_type", "status").annotate(count=Count("id")).order_by("action_type", "status")[:100])
    response = JsonResponse({"source": "core.AgentTask", "stages": rows, "progress_percent": None, "progress_reason": "No verified product-stage linkage", "task_count_in_returned_groups": sum(row["count"] for row in rows), "group_limit": 100, "complete": len(rows) < 100})
    response["Cache-Control"] = "no-store"
    return response
