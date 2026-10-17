"""Deterministic, permission-scoped recommendations: no LLM execution.

All findings are evidence-linked drafts for human review, not real-world actions.
No payments, stock transactions, publishing or external API calls.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_UP
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from enterprise_portal.models import (
    BudgetPlan, CommercialDocument, JournalEntry, InventoryItem,
    StockMovement, WorkTask,
)
from enterprise_portal.services import stock_balance
from .access import require_unit
from .catalog import CATALOG
from .costing import estimate_manufacturing_cost
from .models import (
    AssistantRun, BillOfMaterials, MaintenanceTicket, ManagementRisk,
    PerformanceIndicator, ProductionOrder, ProposedAutomation, ProcurementNeed,
    QualityInspection, StaffAssignment, Timesheet, ManagedSite,
    ProductionCostScenario,
)


# Assistant execution permission is additive to Django's per-app/module grants and
# active unit membership; a generic analyst cannot inspect protected financial,
# employee or customer records merely by possessing add_assistantrun.
HANDLER_VIEW_PERMISSIONS = {
    "executive": ("enterprise_portal.view_worktask", "ecosystem_hub.view_managementrisk",
                  "ecosystem_hub.view_productionorder"),
    "kpi": ("ecosystem_hub.view_performanceindicator",),
    "risk": ("ecosystem_hub.view_managementrisk",),
    "budget": ("enterprise_portal.view_budgetplan",),
    "receivables": ("enterprise_portal.view_commercialdocument",),
    "payables": ("enterprise_portal.view_commercialdocument",),
    "ledger": ("enterprise_portal.view_journalentry",),
    "cost": ("ecosystem_hub.view_productioncostscenario",
             "ecosystem_hub.view_materialpricereference"),
    "reorder": ("enterprise_portal.view_inventoryitem",
                "enterprise_portal.view_stockmovement",
                "ecosystem_hub.view_procurementneed"),
    "production": ("ecosystem_hub.view_productionorder",
                   "ecosystem_hub.view_billofmaterials",
                   "enterprise_portal.view_inventoryitem",
                   "enterprise_portal.view_stockmovement"),
    "quality": ("ecosystem_hub.view_qualityinspection",),
    "maintenance": ("ecosystem_hub.view_maintenanceticket",),
    "people": ("ecosystem_hub.view_timesheet",),
    "tasks": ("enterprise_portal.view_worktask",),
    "sites": ("ecosystem_hub.view_managedsite",),
    "agents": ("ecosystem_hub.view_proposedautomation",),
}


def issue(title, detail, *, severity="info", source=None):
    return {"title": title, "detail": str(detail)[:350],
            "severity": severity, "source": source or "داده داخلی واحد"}


def scan(unit, code):
    """Return at most 30 visible findings, always within the selected unit."""
    definition = CATALOG[code]
    mode = definition["handler"]
    today = timezone.localdate()
    findings = []
    if mode == "reorder":
        for item in InventoryItem.objects.filter(unit=unit, active=True).order_by("sku")[:100]:
            qty = stock_balance(item.pk)
            if qty <= item.reorder_point:
                findings.append(issue(
                    f"بازبینی موجودی {item.sku}",
                    f"موجودی قطعی {qty} {item.measure}؛ نقطه سفارش {item.reorder_point}. "
                    "خرید خودکار انجام نشده است.",
                    severity="warning", source=f"InventoryItem:{item.pk}"))
        pending = ProcurementNeed.objects.filter(unit=unit, status__in=("draft", "review")).count()
        if pending:
            findings.append(issue("درخواست‌های خرید باز", f"{pending} درخواست نیازمند بررسی است."))
    elif mode == "production":
        for order in ProductionOrder.objects.filter(
            unit=unit, state__in=("draft", "review", "approved"),
        ).select_related("formula").order_by("due_date", "pk")[:40]:
            if order.due_date and order.due_date < today:
                findings.append(issue(f"سفارش تولید {order.code} عقب‌افتاده",
                    f"تاریخ تعهد {order.due_date} گذشته است.", severity="warning",
                    source=f"ProductionOrder:{order.pk}"))
            formula = order.formula
            for line in formula.materials.select_related("item").all()[:35]:
                needed = (order.quantity / formula.yield_quantity) * line.quantity
                needed *= (Decimal("1") + line.scrap_percent / Decimal("100"))
                needed = needed.quantize(Decimal("0.001"), rounding=ROUND_UP)
                available = stock_balance(line.item_id)
                if needed > available:
                    findings.append(issue(
                        f"کسری مواد برای سفارش {order.code}: {line.item.sku}",
                        f"نیاز برآوردی {needed}، موجودی قطعی {available} {line.item.measure}. "
                        "این فقط برنامه است، هیچ خروج انباری ثبت نشده.",
                        severity="warning", source=f"MaterialRequirement:{line.pk}"))
    elif mode == "cost":
        scenarios = ProductionCostScenario.objects.filter(
            unit=unit,
        ).select_related("order__formula__product").order_by("-created_at")[:15]
        for scenario in scenarios:
            estimate = estimate_manufacturing_cost(scenario)
            if estimate["complete"]:
                findings.append(issue(
                    "سناریوی هزینه: " + estimate["order_code"],
                    f"برآورد مستند {estimate['total']} {estimate['currency']}؛ "
                    f"بهای واحد {estimate['unit_cost']}؛ فقط برای برنامه‌ریزی، "
                    "نه سند قطعی حسابداری.",
                    source=f"ProductionCostScenario:{scenario.pk}",
                ))
            else:
                findings.append(issue(
                    "نرخ‌های ناکامل سفارش " + estimate["order_code"],
                    "نرخ مستند کافی برای " + (
                        ", ".join(estimate["missing_skus"]) or "مواد اولیه تعریف نشده"
                    ) + " وجود ندارد؛ جمع هزینه محاسبه نمی‌شود.",
                    severity="warning", source=f"ProductionCostScenario:{scenario.pk}",
                ))
    elif mode in ("receivables", "payables"):
        kind = "purchase" if mode == "payables" else "sales"
        q = CommercialDocument.objects.filter(
            unit=unit, kind=kind, due_on__lt=today,
        ).exclude(status__in=("settled", "cancelled"))
        for doc in q.order_by("due_on", "pk")[:40]:
            findings.append(issue(
                f"سررسید سند تجاری {doc.number}",
                f"مبلغ ثبت‌شده {doc.total} {doc.currency}، تاریخ {doc.due_on}. "
                "وضعیت تسویه از اسناد داخلی گرفته شده و با بانک تطبیق نشده است.",
                severity="warning", source=f"CommercialDocument:{doc.pk}"))
    elif mode == "ledger":
        for currency, status, count in (
            JournalEntry.objects.filter(unit=unit)
            .values_list("currency", "status")
            .annotate(count=Count("pk"))
        ):
            findings.append(issue(
                f"دفتر {currency} — {status}",
                f"{count} سند ثبت‌شده؛ تحلیل تراز قطعی باید در گزارش حسابداری بررسی شود."))
    elif mode == "risk":
        qs = ManagementRisk.objects.filter(unit=unit).exclude(state="closed")
        for item in qs.order_by("-impact", "-likelihood")[:40]:
            if item.risk_score >= 12 or (item.due_date and item.due_date < today):
                findings.append(issue(item.title,
                    f"امتیاز ریسک {item.risk_score}/25؛ "
                    f"وضعیت {item.get_state_display()} و اقدام پیشنهادی: {item.mitigation[:140] or 'نیازمند ثبت'}",
                    severity="warning", source=f"ManagementRisk:{item.pk}"))
    elif mode == "maintenance":
        for task in MaintenanceTicket.objects.filter(
            unit=unit, due_date__lt=today,
        ).exclude(status="done").order_by("due_date")[:40]:
            findings.append(issue(task.title,
                f"موعد نگهداری {task.due_date} گذشته است.", severity="warning",
                source=f"MaintenanceTicket:{task.pk}"))
    elif mode == "quality":
        for check in QualityInspection.objects.filter(
            unit=unit, result__in=("fail", "hold"),
        ).order_by("-inspected_on")[:40]:
            findings.append(issue(check.title,
                f"آخرین نتیجه {check.get_result_display()}؛ بررسی علت و اقدام اصلاحی ضروری است.",
                severity="warning", source=f"QualityInspection:{check.pk}"))
    elif mode == "tasks":
        q = WorkTask.objects.filter(unit=unit, due_on__lt=today).exclude(status="done")
        count = q.count()
        if count:
            findings.append(issue("وظایف معوق", f"{count} کار ثبت‌شده از موعد خود عبور کرده است.",
                severity="warning", source="WorkTask"))
    elif mode == "people":
        totals = defaultdict(Decimal)
        for person, hours in Timesheet.objects.filter(
            unit=unit, approved=True,
        ).values_list("person_id", "hours")[:1500]:
            totals[person] += hours
        findings.append(issue("ساعت‌های کارکرد تأییدشده",
            f"{len(totals)} نفر با کارکرد ثبت‌شده. این آمار حقوق یا دستمزد نیست."))
        findings.append(issue("جمع ساعات واحد", f"{sum(totals.values(), Decimal('0'))} ساعت تأییدشده."))
    elif mode == "budget":
        for x in BudgetPlan.objects.filter(unit=unit).order_by("-fiscal_year", "pk")[:40]:
            findings.append(issue(x.title,
                f"{x.amount} {x.currency} برای سال {x.fiscal_year}؛ وضعیت {x.get_status_display()}. "
                "این رقم به‌صورت خودکار با دفاتر مالی تطبیق نشده است.",
                source=f"BudgetPlan:{x.pk}"))
    elif mode == "kpi":
        for k in PerformanceIndicator.objects.filter(unit=unit).order_by("-period", "code")[:40]:
            if k.actual is None:
                findings.append(issue(k.label, f"برای دوره {k.period} هنوز عملکرد واقعی ثبت نشده است.",
                    severity="warning", source=f"PerformanceIndicator:{k.pk}"))
            else:
                findings.append(issue(k.label, f"هدف {k.target}؛ عملکرد ثبت‌شده {k.actual} {k.measurement_unit}.",
                    source=f"PerformanceIndicator:{k.pk}"))
    elif mode == "sites":
        for site in ManagedSite.objects.filter(unit=unit):
            status = site.get_status_display()
            findings.append(issue(site.label,
                f"مسیر: {site.path}؛ وضعیت اعلام‌شده: {status}. "
                "هیچ درخواست شبکه یا بررسی زنده خودکار انجام نشده است.",
                source=f"ManagedSite:{site.pk}"))
    elif mode == "agents":
        rules = ProposedAutomation.objects.filter(unit=unit)
        findings.append(issue("برنامه‌های پیشنهادی اتوماسیون",
            f"{rules.count()} تعریف شده، {rules.filter(active=True).count()} نشان‌گذاری‌شده فعال؛ "
            "وجود نشان فعال، به‌معنای راه‌اندازی واقعی زمان‌بند نیست."))
    elif mode == "executive":
        count = WorkTask.objects.filter(unit=unit).exclude(status="done").count()
        risks = ManagementRisk.objects.filter(unit=unit).exclude(state="closed").count()
        orders = ProductionOrder.objects.filter(unit=unit).exclude(state__in=("closed", "cancelled")).count()
        findings.extend((
            issue("کارهای باز واحد", f"{count} مورد"),
            issue("ریسک‌های باز", f"{risks} مورد"),
            issue("سفارش‌های باز تولید", f"{orders} مورد"),
        ))
    else:
        findings.append(issue("موتور تخصصی هنوز وصل نشده است",
            "در این مرحله، چک‌لیست و گردش بازبینی قابل استفاده است، اما خروجی هوش مصنوعی تخصصی ساخته نشده."))
    if not findings:
        findings = [issue("مورد هشدار ثبت‌شده‌ای یافت نشد",
                          "فقط داده‌های موجود در این واحد بررسی شده‌اند. خالی بودن گزارش اثبات نبود مشکل نیست.")]
    return findings[:30]


@transaction.atomic
def generate_report(actor, unit, code):
    if code not in CATALOG:
        raise ValidationError("دستیار مورد نظر در فهرست سامانه وجود ندارد.")
    require_unit(actor, unit)
    if not (actor.is_superuser or actor.has_perm("ecosystem_hub.add_assistantrun")):
        raise PermissionDenied("مجوز اجرای تحلیل این واحد موجود نیست.")
    for permission_code in HANDLER_VIEW_PERMISSIONS.get(CATALOG[code]["handler"], ()):
        if not (actor.is_superuser or actor.has_perm(permission_code)):
            raise PermissionDenied("برای تحلیل داده‌های این دستیار، مجوز مشاهده اطلاعات منبع لازم است.")
    findings = scan(unit, code)
    report = AssistantRun.objects.create(
        unit=unit, requested_by=actor, assistant_code=code,
        state="draft", findings=findings,
        evidence={"source": "authorized company records, read only",
                  "method": "deterministic rules; no external LLM",
                  "executed_at": timezone.now().isoformat(),
                  "no_external_side_effects": True,
                  "requires_human_review": True,
                  "specialized_engine_connected": bool(CATALOG[code]["handler"])},
    )
    return report
