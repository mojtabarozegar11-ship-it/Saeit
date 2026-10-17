"""Server-rendered, role-filtered ecosystem workspace and assistant drafts."""
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from enterprise_portal.models import BusinessUnit, InventoryItem, JournalEntry, WorkTask
from enterprise_portal.views import office_access, no_cache
from .access import user_units, require_unit
from .analysis import generate_report
from .catalog import CATALOG, DEPARTMENTS
from .models import (
    AssistantRun, ManagementRisk, ManagedSite, ProductionOrder, ProcurementNeed,
    QualityInspection, MaintenanceTicket, ReviewApproval, UnitMembership,
    PerformanceIndicator, ProposedAutomation,
)


def permission(user, codename):
    return bool(user.is_superuser or user.has_perm("ecosystem_hub." + codename))


def require_hub(request):
    if not permission(request.user, "view_organization"):
        raise PermissionDenied("دسترسی به مرکز اکوسیستم مجاز نیست.")


def select_unit(request):
    units = user_units(request.user)
    key = request.GET.get("unit") or request.POST.get("unit")
    if key:
        unit = get_object_or_404(units, code=key)
    else:
        unit = units.order_by("code").first()
    if unit:
        require_unit(request.user, unit)
    return unit, units.order_by("code")


def page(request, template, data):
    return no_cache(render(request, "ecosystem_hub/" + template + ".html", data))


@never_cache
@office_access
@require_GET
def dashboard(request):
    require_hub(request)
    unit, units = select_unit(request)
    result = []
    if unit:
        result = [
            ("سفارش‌های باز تولید", ProductionOrder.objects.filter(unit=unit).exclude(state__in=("closed", "cancelled")).count()),
            ("درخواست‌های تأمین", ProcurementNeed.objects.filter(unit=unit, status__in=("draft", "review")).count()),
            ("کنترل کیفیت نیازمند رسیدگی", QualityInspection.objects.filter(unit=unit, result__in=("fail", "hold")).count()),
            ("ریسک‌های باز", ManagementRisk.objects.filter(unit=unit).exclude(state="closed").count()),
            ("کارهای باز", WorkTask.objects.filter(unit=unit).exclude(status="done").count()),
            ("گزارش‌های دستیار", AssistantRun.objects.filter(unit=unit).count()),
        ]
    return page(request, "dashboard", {
        "selected_unit": unit, "units": units, "cards": result,
        "department_count": len(DEPARTMENTS), "assistant_count": len(CATALOG),
        "assistant_preview": list(CATALOG.values())[:8],
        "section": "ecosystem",
    })


@never_cache
@office_access
@require_GET
def assistants(request):
    require_hub(request)
    unit, units = select_unit(request)
    groups = []
    for key, label in DEPARTMENTS:
        entries = [item for item in CATALOG.values() if item["department"] == key]
        groups.append({"key": key, "label": label, "entries": entries})
    return page(request, "assistants", {
        "selected_unit": unit, "units": units, "groups": groups,
        "can_run": permission(request.user, "add_assistantrun"),
        "section": "assistants",
    })


@never_cache
@office_access
@require_POST
def run_assistant(request, code):
    require_hub(request)
    if code not in CATALOG:
        raise Http404
    unit, _ = select_unit(request)
    if not unit:
        raise Http404("واحد شرکت تعریف نشده است.")
    report = generate_report(request.user, unit, code)
    return no_cache(redirect("enterprise_portal:ecosystem_hub:report", pk=report.pk))


@never_cache
@office_access
@require_GET
def report(request, pk):
    require_hub(request)
    if not permission(request.user, "view_assistantrun"):
        raise PermissionDenied("مجوز مشاهده گزارش‌های دستیار موجود نیست.")
    report = get_object_or_404(
        AssistantRun.objects.select_related("unit", "requested_by").filter(unit__in=user_units(request.user)),
        pk=pk,
    )
    definition = CATALOG.get(report.assistant_code)
    return page(request, "report", {
        "report": report,
        "definition": definition,
        "selected_unit": report.unit,
        "section": "assistants",
    })


@never_cache
@office_access
@require_GET
def production(request):
    require_hub(request)
    unit, units = select_unit(request)
    if not permission(request.user, "view_productionorder"):
        raise PermissionDenied("مجوز مشاهده تولید موجود نیست.")
    orders = []
    if unit:
        orders = ProductionOrder.objects.filter(unit=unit).select_related(
            "formula", "formula__product", "work_center",
        ).order_by("due_date", "-pk")[:60]
    return page(request, "production", {
        "selected_unit": unit, "units": units, "orders": orders,
        "section": "production",
    })


@never_cache
@office_access
@require_GET
def oversight(request):
    require_hub(request)
    unit, units = select_unit(request)
    if not permission(request.user, "view_managementrisk"):
        raise PermissionDenied("مجوز مشاهده ریسک و کنترل وجود ندارد.")
    risks = ManagementRisk.objects.filter(unit=unit).exclude(state="closed").order_by("-impact", "-likelihood")[:60] if unit else []
    approvals = ReviewApproval.objects.filter(unit=unit, decision="pending").order_by("-created_at")[:25] if unit and permission(request.user, "view_reviewapproval") else []
    return page(request, "oversight", {
        "selected_unit": unit, "units": units, "risks": risks,
        "approvals": approvals, "section": "oversight",
    })


@never_cache
@office_access
@require_GET
def modules(request):
    require_hub(request)
    unit, units = select_unit(request)
    return page(request, "modules", {
        "selected_unit": unit, "units": units, "section": "modules",
        "stats": [
            ("مراکز و فرمول‌های تولید", "فرمول مواد، ظرفیت، سفارش ساخت و برنامه"),
            ("تدارکات و بازرگانی", "نیاز خرید، قراردادها و بررسی تأمین‌کننده"),
            ("کیفیت و تعمیرات", "بازرسی تولید و برنامه سرویس ماشین‌آلات"),
            ("منابع انسانی", "سمت‌ها، کارکرد و کنترل وظایف سازمانی"),
            ("شاخص‌ها و ریسک", "هدف‌های واحد، اقدام اصلاحی، پیگیری مصوبات"),
            ("شرکت‌ها و زیرسایت‌ها", "شناسه و دسترسی هر واحد، و فهرست مسیرهای محافظت‌شده"),
            ("حسابرسی و شواهد", "ارجاع سند، اثرانگشت محتوا و مسیر تأیید انسانی"),
            ("برنامه‌های اتوماسیون", "پیشنهاد زمان‌بندی؛ هیچ اجرای خودکاری بدون موتور و تأیید واقعی"),
        ],
    })
