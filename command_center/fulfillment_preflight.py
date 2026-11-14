"""Owner-only diagnostic; never issue digital downloads or mail buyers."""
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.chat_operation_security import is_authorized_chat_operator
from core.fulfillment_preflight import fulfillment_preflight_snapshot


@never_cache
@require_GET
def fulfillment_preflight_api(request):
    if not is_authorized_chat_operator(getattr(request, "user", None)):
        response = JsonResponse(
            {"detail": "Active owner required for private delivery readiness."},
            status=403,
        )
    else:
        response = JsonResponse(fulfillment_preflight_snapshot())
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
