"""MojPlayWin-only, staff-authenticated, read-only runtime monitoring pages."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.db import DatabaseError
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .mpw_private_telemetry import snapshot
from core.mojtaba_site_receipts import inspect_public_monitor_continuity

_ALLOWED_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))


def _require_mpw(request):
    if request.get_host().split(":")[0].lower() not in _ALLOWED_HOSTS:
        raise Http404("This private monitoring page is scoped to MojPlayWin.")


@staff_member_required
@require_GET
def dashboard(request):
    _require_mpw(request)
    response = render(request, "command_center/mpw_agent_monitor.html")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@staff_member_required
@require_GET
def telemetry_api(request):
    _require_mpw(request)
    result = snapshot()
    # Transitional dual-read: legacy collector remains the source for Gen64/65,
    # 77 library slots and private-worker state; the canonical bot contributes
    # *only* its own redacted public-route receipts.
    try:
        canonical = inspect_public_monitor_continuity()["sites"]["mojplaywin"]
    except DatabaseError:
        # Preserve the current private dashboard when the Django audit DB is
        # unavailable. Never claim that a missing record is a healthy agent.
        canonical = {"state": "auditlog_unavailable",
                     "public_monitor_continuity_observed": False}
    result["canonical_public_monitor"] = {
        **canonical,
        "canonical_bot": "mojtaba.bot.ai",
        "other_tenant_data_exposed": False,
        "private_worker_replaced": False,
        "legacy_collector_retirement_authorized": False,
    }
    response = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
