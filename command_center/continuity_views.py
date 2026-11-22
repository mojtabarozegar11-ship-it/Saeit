"""Private continuity state; GET never performs writes."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .continuity import run_continuity_cycle


@staff_member_required
@require_GET
def continuity_status(request):
    response = JsonResponse(run_continuity_cycle())
    response["Cache-Control"] = "no-store"
    return response
