"""Staff-only read-only command center; no inferred production health."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .overview import build_overview
from .catalog import MODULES, AGENT_SETTINGS, localized
from core.models import Agent, ApprovalRequest, NewsletterStory
from django.contrib.auth import get_user_model

COMPONENTS = ("factory", "iran_site", "global_site", "master_agent", "agents", "bots", "vps", "cpanel", "github")

@staff_member_required
@require_GET
def dashboard(request):
    lang = request.GET.get("lang", "fa")
    if lang not in ("fa", "en"):
        lang = "fa"
    response = render(request, "command_center/dashboard.html", {
        "components": COMPONENTS, "lang": lang,
        "modules": localized(MODULES, lang),
        "agent_settings": localized(AGENT_SETTINGS, lang),
        "workflow_stages": [{"label": name} for name in ("Research", "Design", "Development", "Quality assurance", "Packaging", "Publishing", "Delivery")],
        "staff_counts": {
            "agents": Agent.objects.count(),
            "staff": get_user_model().objects.filter(is_staff=True, is_active=True).count(),
            "approvals": ApprovalRequest.objects.filter(status="pending").count(),
            "drafts": NewsletterStory.objects.filter(status="draft").count(),
        },
    })
    response["Cache-Control"] = "no-store"
    return response

@staff_member_required
@require_GET
def overview_api(request):
    # No adapter connected: empty observations and workstreams are intentionally unknown.
    data = build_overview([], {})
    data["expected_components"] = [{"id": name, "state": "unknown", "reason": "adapter_not_connected"} for name in COMPONENTS]
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response
