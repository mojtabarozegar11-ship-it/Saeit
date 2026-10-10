"""Read-only approval queue. Decisions use the existing owner-only API."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.models import ApprovalRequest

@staff_member_required
@require_GET
def pending(request):
    rows = ApprovalRequest.objects.filter(
        status="pending"
    ).order_by("-created_at").values(
        "id", "action_type", "target_type", "target_id",
        "risk", "created_at", "requested_by_id"
    )[:100]
    response = JsonResponse({
        "items": list(rows),
        "truncated": ApprovalRequest.objects.filter(status="pending").count() > 100,
        "decision_endpoint": "/api/approvals/{id}/decide/",
        "decisions_require_designated_owner": True,
    })
    response["Cache-Control"] = "no-store"
    return response
