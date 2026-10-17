"""Server-rendered, role-filtered ecosystem workspace and assistant drafts."""
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from enterprise_portal.models import BusinessUnit, InventoryItem, JournalEntry, JournalLine, WorkTask, AuditEvent
from enterprise_portal.views import office_access, no_cache
from .access import user_units, require_unit
from .analysis import generate_report
from .costing import estimate_manufacturing_cost
from .procurement import material_shortages, prepare_purchase_drafts
from .catalog import CATALOG, DEPARTMENTS
from .models import (
    AssistantRun, ManagementRisk, ManagedSite, ProductionOrder, ProcurementNeed,
    Organization, AssistantFollowUp,
    QualityInspection, MaintenanceTicket, ReviewApproval, UnitMembership,
    PerformanceIndicator, ProposedAutomation, ProductionCostScenario,
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
def group_overview(request):
    """Owner-only group control, not consolidated legal financial statements."""
    require_hub(request)
    if not request.user.is_superuser:
        raise PermissionDenied("مقایسه همه شرکت‌ها فقط با دسترسی مدیر ارشد مجاز است.")
    units = list(BusinessUnit.objects.order_by("code"))
    identities = {x.unit_id: x for x in Organization.objects.select_related("parent", "unit")}
    ledger_groups = list(
        JournalLine.objects.filter(entry__status="posted")
        .values("entry__unit_id", "entry__currency")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("entry__unit_id", "entry__currency")
    )
    finance_by_unit = {}
    for record in ledger_groups:
        finance_by_unit.setdefault(record["entry__unit_id"], []).append({
            "currency": record["entry__currency"],
            "debit": record["debit"],
            "credit": record["credit"],
        })
    production = {
        x["unit_id"]: x["total"] for x in
        ProductionOrder.objects.exclude(state__in=("closed", "cancelled"))
        .values("unit_id").annotate(total=Count("pk"))
    }
    risks = {
        x["unit_id"]: x["total"] for x in
        ManagementRisk.objects.exclude(state="closed")
        .values("unit_id").annotate(total=Count("pk"))
    }
    work = {
        x["unit_id"]: x["total"] for x in
        WorkTask.objects.exclude(status="done").values("unit_id").annotate(total=Count("pk"))
    }
    rows = [{
        "unit": unit,
        "identity": identities.get(unit.id),
        "journals": finance_by_unit.get(unit.id, []),
        "production": production.get(unit.id, 0),
        "risks": risks.get(unit.id, 0),
        "tasks": work.get(unit.id, 0),
    } for unit in units]
    return page(request, "group", {
        "rows": rows, "unit_count": len(units), "section": "group",
        "selected_unit": None, "units": units,
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
    user_model = get_user_model()
    approvers = user_model.objects.filter(
        Q(is_superuser=True) |
        Q(ecosystem_memberships__unit=report.unit,
          ecosystem_memberships__active=True,
          ecosystem_memberships__can_approve=True),
        is_active=True, is_staff=True,
    ).distinct().order_by("username")[:40]
    can_request_approval = (
        permission(request.user, "add_reviewapproval") and
        (request.user.is_superuser or report.requested_by_id == request.user.pk)
    )
    try:
        require_unit(request.user, report.unit, write=True)
        can_create_followup = (
            permission(request.user, "add_assistantfollowup")
            and request.user.has_perm("enterprise_portal.add_worktask")
        )
    except PermissionDenied:
        can_create_followup = False
    assignees = user_model.objects.filter(
        Q(is_superuser=True) |
        Q(ecosystem_memberships__unit=report.unit, ecosystem_memberships__active=True),
        is_active=True, is_staff=True,
    ).distinct().order_by("username")[:50] if can_create_followup else []
    followed_indices = list(AssistantFollowUp.objects.filter(
        report=report).values_list("finding_index", flat=True))
    return page(request, "report", {
        "approvers": approvers,
        "can_request_approval": can_request_approval,
        "assignees": assignees,
        "can_create_followup": can_create_followup,
        "followed_indices": followed_indices,
        "report": report,
        "definition": definition,
        "selected_unit": report.unit,
        "section": "assistants",
    })




@never_cache
@office_access
@require_POST
@transaction.atomic
def create_followup(request, pk):
    """Create a delegated human task, never a payment or autonomous command."""
    require_hub(request)
    if not (permission(request.user, "add_assistantfollowup")
            and request.user.has_perm("enterprise_portal.add_worktask")):
        raise PermissionDenied("مجوز ثبت پیگیری و وظیفه سازمانی لازم است.")
    report = get_object_or_404(
        AssistantRun.objects.select_for_update().select_related("unit")
        .filter(unit__in=user_units(request.user)),
        pk=pk,
    )
    require_unit(request.user, report.unit, write=True)
    try:
        index = int(request.POST.get("finding_index", ""))
        assignee_id = int(request.POST.get("assignee_id", ""))
    except (ValueError, TypeError):
        raise Http404("یافته یا مسئول انتخاب‌شده معتبر نیست.")
    if index < 0 or not isinstance(report.findings, list) or index >= len(report.findings):
        raise Http404("یافته گزارش وجود ندارد.")
    existing = AssistantFollowUp.objects.filter(report=report, finding_index=index).first()
    if existing:
        return no_cache(redirect("enterprise_portal:ecosystem_hub:report", pk=report.pk))
    assignee = get_object_or_404(
        get_user_model().objects.filter(
            Q(is_superuser=True) |
            Q(ecosystem_memberships__unit=report.unit, ecosystem_memberships__active=True),
            is_active=True, is_staff=True).distinct(),
        pk=assignee_id,
    )
    finding = report.findings[index]
    if not isinstance(finding, dict):
        raise Http404("فرمت یافته قابل ارجاع نیست.")
    title = str(finding.get("title") or "یافته دستیار").strip()[:200]
    detail = str(finding.get("detail") or "").strip()[:700]
    source = str(finding.get("source") or "گزارش داخلی")[:180]
    task = WorkTask.objects.create(
        title="پیگیری: " + (title or "یافته دستیار"),
        description=(
            f"گزارش دستیار {report.pk} / یافته {index + 1}\n"
            f"شاهد: {source}\n{detail}\n"
            "این فقط وظیفه داخلی است؛ هیچ اقدام مالی یا تولیدی اجرا نشده است."
        ),
        unit=report.unit,
        assigned_to=assignee,
        created_by=request.user,
        priority="high" if finding.get("severity") == "warning" else "normal",
        status="todo",
    )
    record = AssistantFollowUp.objects.create(
        unit=report.unit, report=report, finding_index=index,
        task=task, created_by=request.user,
    )
    AuditEvent.objects.create(
        actor=request.user, action="assistant_followup_created",
        target=f"WorkTask:{task.pk}",
        detail={"unit_id": report.unit_id, "report_id": report.pk,
                "finding_index": index, "followup_id": record.pk,
                "no_external_side_effects": True},
    )
    return no_cache(redirect("enterprise_portal:ecosystem_hub:report", pk=report.pk))



@never_cache
@office_access
@require_POST
@transaction.atomic
def request_review(request, pk):
    """Queue only a human review of a draft; never execute its findings."""
    require_hub(request)
    if not permission(request.user, "add_reviewapproval"):
        raise PermissionDenied("مجوز درخواست بازبینی مدیریتی را ندارید.")
    report = get_object_or_404(
        AssistantRun.objects.select_for_update().select_related("unit")
        .filter(unit__in=user_units(request.user)),
        pk=pk,
    )
    if not request.user.is_superuser and report.requested_by_id != request.user.pk:
        raise PermissionDenied("تنها درخواست‌دهنده گزارش می‌تواند آن را ارجاع دهد.")
    user_model = get_user_model()
    approver_pk = request.POST.get("approver_id")
    approver = get_object_or_404(
        user_model.objects.filter(is_active=True, is_staff=True)
        .filter(Q(is_superuser=True) |
                Q(ecosystem_memberships__unit=report.unit,
                  ecosystem_memberships__active=True,
                  ecosystem_memberships__can_approve=True)).distinct(),
        pk=approver_pk,
    )
    scope = {
        "unit": report.unit,
        "target_type": "assistant_report",
        "target_reference": str(report.pk),
        "requested_by": request.user,
    }
    existing = ReviewApproval.objects.filter(**scope, decision="pending").first()
    if not existing:
        entry = ReviewApproval.objects.create(
            **scope,
            summary="بازبینی گزارش " + report.assistant_code,
            assigned_to=approver,
        )
        AuditEvent.objects.create(
            actor=request.user, action="ecosystem_review_requested",
            target=f"AssistantRun:{report.pk}",
            detail={"unit_id": report.unit_id, "approval_id": entry.pk,
                    "no_execution": True},
        )
    if report.state == "draft":
        report.state = "review"
        report.save(update_fields=("state", "updated_at"))
    return no_cache(redirect("enterprise_portal:ecosystem_hub:report", pk=report.pk))



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
    scenarios = ProductionCostScenario.objects.filter(unit=unit).select_related(
        "order", "order__formula__product"
    ).order_by("-created_at")[:50] if unit and permission(request.user, "view_productioncostscenario") else []
    return page(request, "production", {
        "selected_unit": unit, "units": units, "orders": orders,
        "scenarios": scenarios, "section": "production",
    })




def _can_plan_materials(user):
    return bool(user.is_superuser or (
        user.has_perm("ecosystem_hub.view_productionorder")
        and user.has_perm("ecosystem_hub.view_billofmaterials")
        and user.has_perm("enterprise_portal.view_inventoryitem")
        and user.has_perm("enterprise_portal.view_stockmovement")
    ))


@never_cache
@office_access
@require_GET
def production_material_plan(request, pk):
    require_hub(request)
    if not _can_plan_materials(request.user):
        raise PermissionDenied("برای مشاهده نیاز مواد باید مجوز مشاهده تولید و انبار داشته باشید.")
    order = get_object_or_404(
        ProductionOrder.objects.filter(unit__in=user_units(request.user))
        .select_related("formula", "unit", "formula__product"),
        pk=pk,
    )
    materials = material_shortages(order)
    draft_refs = ProcurementNeed.objects.filter(
        unit=order.unit, reference__startswith=f"MRP-{order.pk}-",
    ).select_related("item").order_by("reference") if permission(request.user, "view_procurementneed") else []
    allow_create = permission(request.user, "add_procurementneed")
    if not request.user.is_superuser:
        allow_create = allow_create and UnitMembership.objects.filter(
            user=request.user, unit=order.unit, active=True,
            role__in=("owner", "manager", "finance", "operations"),
        ).exists()
    return page(request, "materials", {
        "selected_unit": order.unit, "order": order, "materials": materials,
        "draft_refs": draft_refs, "allow_create": allow_create,
        "section": "production",
    })


@never_cache
@office_access
@require_POST
def create_procurement_drafts(request, pk):
    require_hub(request)
    if not permission(request.user, "add_procurementneed"):
        raise PermissionDenied("مجوز ثبت پیش‌نویس درخواست خرید را ندارید.")
    if not _can_plan_materials(request.user):
        raise PermissionDenied("پیش از درخواست خرید، مجوز مشاهده تولید و انبار لازم است.")
    order = get_object_or_404(
        ProductionOrder.objects.filter(unit__in=user_units(request.user)),
        pk=pk,
    )
    require_unit(request.user, order.unit, write=True)
    try:
        prepare_purchase_drafts(order.pk, request.user)
    except ValidationError as error:
        return no_cache(HttpResponseBadRequest(str(error)))
    return no_cache(redirect("enterprise_portal:ecosystem_hub:material_plan", pk=order.pk))



@never_cache
@office_access
@require_GET
def production_cost(request, pk):
    require_hub(request)
    if not permission(request.user, "view_productioncostscenario") or not permission(
        request.user, "view_materialpricereference"
    ):
        raise PermissionDenied("مشاهده برآورد قیمت مواد مستلزم مجوز مالی و تولید است.")
    scenario = get_object_or_404(
        ProductionCostScenario.objects.filter(unit__in=user_units(request.user))
        .select_related("unit", "order__formula__product"),
        pk=pk,
    )
    result = estimate_manufacturing_cost(scenario)
    return page(request, "cost", {
        "scenario": scenario, "cost": result, "selected_unit": scenario.unit,
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
