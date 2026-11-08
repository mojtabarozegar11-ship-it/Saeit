"""Management desk operational summary and safe staff-only work item endpoints."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count
from .models import WorkItem, InternalMessage, PrivateAuction


@staff_member_required
@require_GET
def operations_summary(request):
    done = WorkItem.objects.filter(status="done")
    with_reference = done.exclude(resolution_reference="").count()
    without_reference = done.filter(resolution_reference="").count()
    data = {
        "work_items": {
            "total": WorkItem.objects.count(),
            "open": WorkItem.objects.filter(status="open").count(),
            "in_progress": WorkItem.objects.filter(status="in_progress").count(),
            "blocked": WorkItem.objects.filter(status="blocked").count(),
            "done": with_reference + without_reference,
            # Presence of a reference is NOT independent outcome verification.
            "done_with_reference_unverified": with_reference,
            "done_without_reference": without_reference,
        },
        "messages": {
            "unread": InternalMessage.objects.filter(recipient=request.user, read_at__isnull=True).count(),
            "sent": InternalMessage.objects.filter(sender=request.user).count(),
        },
        "auctions": {
            "draft": PrivateAuction.objects.filter(status="draft").count(),
            "open": PrivateAuction.objects.filter(status="open").count(),
            "closed": PrivateAuction.objects.filter(status="closed").count(),
        },
    }
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response
