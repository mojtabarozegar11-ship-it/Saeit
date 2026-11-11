"""Staff-only projection of legacy Agent records under one public bot identity."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.models import Agent
from .unified_identity import identity_snapshot


@staff_member_required
@require_GET
def directory(request):
    rows = list(Agent.objects.order_by("code").values(
        "id", "code", "name", "mission", "risk_level", "active",
    )[:200])
    total = Agent.objects.count()
    response = JsonResponse(identity_snapshot(rows, total))
    response["Cache-Control"] = "no-store"
    return response
