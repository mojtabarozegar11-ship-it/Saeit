"""MojPlayWin-only, staff-authenticated, read-only runtime monitoring pages."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .mpw_private_telemetry import snapshot

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
    response = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
