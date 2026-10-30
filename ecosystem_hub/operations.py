"""Read-only control room for unit-scoped assistant rules and verifiable reports.

An 'active' database flag is not proof of a cron worker. Monitoring never
invokes an agent or makes payment/stock/content changes.
"""
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.utils import timezone

from enterprise_portal.views import office_access
from .catalog import CATALOG
from .management.commands.run_ecosystem_assistants import is_due
from .models import AssistantRun, ProposedAutomation, UnitMembership
from .report_policy import permitted_assistant_codes
from .views import require_hub, permission, select_unit, page


@never_cache
@office_access
@require_GET
def operations(request):
    require_hub(request)
    if not (
        permission(request.user, "view_assistantrun")
        and permission(request.user, "view_proposedautomation")
    ):
        raise PermissionDenied("برای پایش دستیارها به مجوز گزارش و تنظیمات زمان‌بندی نیاز است.")

    unit, units = select_unit(request)
    schedules = []
    reports = []
    if unit:
        manager = request.user.is_superuser or UnitMembership.objects.filter(
            user=request.user, unit=unit, active=True, role__in=("owner", "manager"),
        ).exists()
        active_rules = ProposedAutomation.objects.filter(unit=unit)
        visible_runs = AssistantRun.objects.filter(
            unit=unit, assistant_code__in=permitted_assistant_codes(request.user),
        )
        if not manager:
            active_rules = active_rules.filter(owner=request.user)
            visible_runs = visible_runs.filter(requested_by=request.user)

        now = timezone.now()
        for rule in active_rules.select_related("owner").order_by("assistant_code", "pk")[:80]:
            item = CATALOG.get(rule.assistant_code)
            schedules.append({
                "code": rule.assistant_code,
                "title": item["title"] if item else "دستیار تعریف‌نشده",
                "owner": rule.owner,
                "cadence": rule.get_cadence_display(),
                "active": rule.active,
                "last_checked": rule.last_checked_at,
                "due": is_due(rule, now=now),
                "engine_available": bool(item and item["handler"]),
            })
        for saved in visible_runs.select_related("requested_by").order_by("-generated_at", "-pk")[:40]:
            item = CATALOG.get(saved.assistant_code)
            reports.append({
                "report": saved,
                "title": item["title"] if item else "دستیار ناشناخته",
                "findings": len(saved.findings) if isinstance(saved.findings, list) else 0,
            })

    return page(request, "operations", {
        "selected_unit": unit,
        "units": units,
        "schedules": schedules,
        "reports": reports,
        "schedule_count": len(schedules),
        "report_count": len(reports),
        "section": "assistant_operations",
        "worker_verified": False,
    })
