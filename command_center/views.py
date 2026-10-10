"""Staff-only read-only command center; no inferred production health."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .overview import build_overview

COMPONENTS = ("factory", "iran_site", "global_site", "master_agent", "agents", "bots", "vps", "cpanel", "github")

@staff_member_required
@require_GET
def dashboard(request):
    return render(request, "command_center/dashboard.html", {"components": COMPONENTS})

@staff_member_required
@require_GET
def overview_api(request):
    # No adapter connected: empty observations and workstreams are intentionally unknown.
    data = build_overview([], {})
    data["expected_components"] = [{"id": name, "state": "unknown", "reason": "adapter_not_connected"} for name in COMPONENTS]
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response
