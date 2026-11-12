"""Staff-only projection of legacy Agent records under one public bot identity."""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET
from core.models import Agent
from .unified_identity import identity_snapshot


@staff_member_required
@require_GET
def directory(request):
    try:
        offset = int(request.GET.get("offset", "0"))
        if offset < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid module offset")
    page_size = 200  # Resource page size only, not a limit on total modules.
    rows = list(Agent.objects.order_by("code").values(
        "id", "code", "name", "mission", "risk_level", "active",
    )[offset:offset + page_size])
    total = Agent.objects.count()
    payload = identity_snapshot(rows, total, offset=offset)
    if request.path.rstrip("/").endswith("/api/agents/directory"):
        # Read-only compatibility for existing dashboards; not a second bot.
        payload["agents"] = rows
        payload["limit"] = page_size
    response = JsonResponse(payload)
    response["Cache-Control"] = "no-store"
    return response
