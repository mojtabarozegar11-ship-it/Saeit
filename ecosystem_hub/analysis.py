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
from company_marketing.models import Campaign, Lead, Publication
from .access import require_unit
from .catalog import CATALOG
from .manual_guides import MANUAL_GUIDES
from .costing import estimate_manufacturing_cost
from .task_watch import watch_for_unit
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
    "marketing": ("company_marketing.view_campaign",
                  "company_marketing.view_lead",
                  "company_marketing.view_publication"),
}


def issue(title, detail, *, severity="info", source=None):
    return {"title": title, "detail": str(detail)[:350],
            "severity": severity, "source": source or "داده داخلی واحد"}


def scan(unit, code, *, actor):
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
        watch = watch_for_unit(unit, actor=actor, today=today, limit=8)
        counts = watch["counts"]
        findings.extend((
            issue("وظایف معوق", f'{counts["overdue"]} کار باز از موعد گذشته است.',
                  severity="warning" if counts["overdue"] else "info", source="WorkTask"),
            issue("سررسیدهای نزدیک", f'امروز {counts["due_today"]} و هفت روز آینده {counts["due_soon"]} کار باز؛ '
                  f'{counts["no_due"]} کار بدون سررسید.', source="WorkTask"),
            issue("وظایف فوری", f'{counts["urgent"]} کار فوریِ باز نیازمند اولویت‌بندی مدیر است.',
                  severity="warning" if counts["urgent"] else "info", source="WorkTask"),
        ))
        for task in watch["tasks"]:
            due = task.due_on.isoformat() if task.due_on else "بدون سررسید"
            findings.append(issue(
                "پیگیری: " + task.title,
                f"مسئول: {task.assigned_to.username}؛ سررسید: {due}؛ "
                f"اولویت: {task.get_priority_display()}؛ وضعیت: {task.get_status_display()}. "
                "تغییر وضعیت و اقدام اجرایی نیازمند ثبت انسانی است.",
                severity="warning" if task.due_on and task.due_on < today else "info",
                source=f"WorkTask:{task.pk}",
            ))
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
    elif mode == "marketing":
        campaigns = Campaign.objects.filter(unit=unit)
        active = campaigns.filter(status="active")
        leads = Lead.objects.filter(unit=unit)
        open_leads = leads.exclude(stage__in=("won", "lost"))
        queued = Publication.objects.filter(campaign__unit=unit, status="approved")
        due_posts = queued.filter(scheduled_at__lte=timezone.now())
        findings.extend((
            issue("وضعیت کمپین‌ها",
                  f"{campaigns.count()} کمپین ثبت‌شده؛ {active.count()} فعال. "
                  "بودجه سقف برنامه است، نه هزینه واقعی.", source="Campaign"),
            issue("قیف سرنخ‌های فروش",
                  f"{leads.count()} سرنخ ثبت‌شده؛ {open_leads.count()} باز و نیازمند پیگیری. "
                  "سرنخ، فروش قطعی نیست.", source="Lead"),
            issue("انتشارهای بازاریابی در صف",
                  f"{queued.count()} محتوای تأییدشده و هنوز پذیرش‌نشده؛ "
                  f"{due_posts.count()} موعدرسیده. انتشار خودکار انجام نشد.",
                  severity="warning" if due_posts.exists() else "info",
                  source="Publication"),
        ))
        for campaign in active.filter(ends_on__lt=today).order_by("ends_on", "pk")[:10]:
            findings.append(issue(
                "کمپین فعال با پایان گذشته: " + campaign.title,
                f"موعد پایان ثبت‌شده {campaign.ends_on} گذشته است؛ وضعیت دستی نیازمند بررسی است.",
                severity="warning", source=f"Campaign:{campaign.pk}",
            ))
        for publication in due_posts.order_by("scheduled_at", "pk")[:8]:
            findings.append(issue(
                "انتشار موعدرسیده: " + publication.title,
                f"برنامه انتشار {publication.scheduled_at.isoformat()}؛ وضعیت هنوز تأییدشده است. "
                "برای ارسال به سرویس‌دهنده اقدام خودکاری انجام نشد.",
                severity="warning", source=f"Publication:{publication.pk}",
            ))
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
        watch = watch_for_unit(unit, actor=actor, today=today, limit=5)
        counts = watch["counts"]
        risks = ManagementRisk.objects.filter(unit=unit).exclude(state="closed").count()
        orders = ProductionOrder.objects.filter(unit=unit).exclude(state__in=("closed", "cancelled")).count()
        findings.extend((
            issue("کارهای باز واحد", f'{counts["open"]} مورد'),
            issue("هشدار تقویم هوشمند",
                  f'معوق {counts["overdue"]}، امروز {counts["due_today"]}، '
                  f'هفت روز آینده {counts["due_soon"]}، فوری {counts["urgent"]}.',
                  severity="warning" if counts["overdue"] else "info", source="WorkTask"),
            issue("ریسک‌های باز", f"{risks} مورد"),
            issue("سفارش‌های باز تولید", f"{orders} مورد"),
        ))
        for task in watch["tasks"]:
            findings.append(issue(
                "پیگیری مدیریتی: " + task.title,
                f"مسئول: {task.assigned_to.username}؛ "
                f"سررسید: {task.due_on.isoformat() if task.due_on else 'تعیین‌نشده'}؛ "
                f"وضعیت: {task.get_status_display()}.",
                severity="warning" if task.due_on and task.due_on < today else "info",
                source=f"WorkTask:{task.pk}",
            ))
    else:
        findings.append(issue(
            "موتور تخصصی هنوز وصل نشده است",
            "این خروجی چک‌لیست انسانی است؛ دستیار تخصصی یا هوش مصنوعی"
            " مستقل فعال نیست و هیچ داده منبعی خودکار بررسی نشده است.",
            source="اعلام وضعیت فنی",
        ))
        for subject, evidence_needed in MANUAL_GUIDES.get(code, ()):
            findings.append(issue(
                "اقدام پیشنهادی برای بررسی: " + subject,
                evidence_needed + " نتیجه تنها بعد از جمع‌آوری مدرک و تأیید مسئول معتبر است.",
                source="الگوی تخصصی انسانی؛ مدرک هنوز ارائه نشده",
            ))
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
    findings = scan(unit, code, actor=actor)
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
