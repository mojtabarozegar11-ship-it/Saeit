"""Staff-only operational alerts and audit summary."""
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import WorkItem
from core.models import AuditLog


@staff_member_required
@require_GET
def controls_summary(request):
    now = timezone.now()
    overdue = WorkItem.objects.filter(
        due_at__lt=now, due_at__isnull=False
    ).exclude(status="done").count()
    blocked = WorkItem.objects.filter(status="blocked").count()
    recent_audit = AuditLog.objects.filter(
        created_at__gte=now - timedelta(hours=24)
    ).count()
    alerts = []
    if overdue:
        alerts.append({"code": "overdue_work", "severity": "high", "count": overdue, "message": "کار عقب‌افتاده نیازمند اقدام است."})
    if blocked:
        alerts.append({"code": "blocked_work", "severity": "medium", "count": blocked, "message": "کار متوقف‌شده برای رفع مانع وجود دارد."})
    return JsonResponse({
        "captured_at": now.isoformat(),
        "alerts": alerts,
        "audit": {"last_24h": recent_audit},
        "work": {"overdue": overdue, "blocked": blocked},
    })
