"""Unified, read-only management report for the staff desk."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from accounting.models import JournalEntry
from command_center.models import WorkItem, InternalMessage, PrivateAuction
from core.models import ApprovalRequest, ResearchProject


@staff_member_required
@require_GET
def management_report(request):
    now = timezone.now()
    data = {
        "captured_at": now.isoformat(),
        "accounting": {
            "posted": JournalEntry.objects.filter(status=JournalEntry.Status.POSTED).count(),
            "draft": JournalEntry.objects.filter(status=JournalEntry.Status.DRAFT).count(),
        },
        "work": {
            "open": WorkItem.objects.filter(status="open").count(),
            "in_progress": WorkItem.objects.filter(status="in_progress").count(),
            "blocked": WorkItem.objects.filter(status="blocked").count(),
            "done": WorkItem.objects.filter(status="done").count(),
        },
        "communications": {
            "unread_for_me": InternalMessage.objects.filter(recipient=request.user, read_at__isnull=True).count(),
        },
        "auctions": {
            "draft": PrivateAuction.objects.filter(status="draft").count(),
            "open": PrivateAuction.objects.filter(status="open").count(),
        },
        "approvals": {
            "pending": ApprovalRequest.objects.filter(status="pending").count(),
        },
        "projects": {
            "active_or_draft": ResearchProject.objects.exclude(status__in=["done", "closed", "archived"]).count(),
        },
    }
    response = JsonResponse(data)
    response["Cache-Control"] = "no-store"
    return response
