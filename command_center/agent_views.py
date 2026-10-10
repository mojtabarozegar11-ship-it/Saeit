"""Staff-only, read-only operational database snapshot."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .adapters import snapshot

@staff_member_required
@require_GET
def metrics(request):
    response = JsonResponse(snapshot())
    response["Cache-Control"] = "no-store"
    return response
