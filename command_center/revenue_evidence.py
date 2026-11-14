"""Owner-only, read-only sales-to-settlement evidence dashboard.

No customer identity, addresses, wallet transactions or secret provider IDs.
This is NOT a payment verification service and cannot certify cash receipt.
"""
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from core.chat_operation_security import is_authorized_chat_operator
from core.revenue_evidence_gate import revenue_evidence_snapshot


@never_cache
@require_GET
def revenue_evidence_api(request):
    if not is_authorized_chat_operator(getattr(request, "user", None)):
        response = JsonResponse(
            {"detail": "Active owner required for revenue evidence."},
            status=403,
        )
    else:
        response = JsonResponse(revenue_evidence_snapshot())
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response
