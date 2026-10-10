"""Read-only agent directory for the staff command center."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.models import Agent

@staff_member_required
@require_GET
def directory(request):
    rows = Agent.objects.order_by("code").values(
        "id", "code", "name", "mission", "risk_level", "active"
    )[:200]
    response = JsonResponse({
        "agents": list(rows),
        "limit": 200,
        "truncated": Agent.objects.count() > 200,
        "changes_require_approval": True,
    })
    response["Cache-Control"] = "no-store"
    return response
