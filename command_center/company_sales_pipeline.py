"""Owner-only, no-store CRM overview of actual inbound requests."""
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from core.chat_operation_security import is_authorized_chat_operator
from core.company_sales_pipeline import sales_pipeline_snapshot


@never_cache
@require_GET
def company_sales_pipeline_api(request):
    if not is_authorized_chat_operator(getattr(request, "user", None)):
        response = JsonResponse({"detail": "Active owner required."}, status=403)
    else:
        response = JsonResponse(sales_pipeline_snapshot())
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    return response
