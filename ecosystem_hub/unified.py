"""Read-only, unit-scoped view for Zomorod Melal's private business desk.

Counts are not evidence of autonomous execution. No payments, inventory posting,
external messages, factory machines, or deployments are triggered here.
"""
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from enterprise_portal.views import office_access
from enterprise_portal.models import CommercialDocument, JournalEntry, ManagementProject, WorkTask
from company_marketing.models import Campaign, Lead, Publication
from company_messaging.models import Message
from .models import AssistantRun, ProcurementNeed, ProductionOrder, ProposedAutomation, QualityInspection
from .views import page, require_hub, select_unit


def _metric(user, permission, label, queryset):
    # Never query a sensitive model for a user without its view permission.
    if not (user.is_superuser or user.has_perm(permission)):
        return None
    return {"label": label, "count": queryset.count()}


def _section(title, *metrics):
    visible = [metric for metric in metrics if metric is not None]
    return {"title": title, "metrics": visible} if visible else None


def snapshot_for_unit(user, unit, *, today=None):
    """The caller must pass a business unit returned by select_unit()."""
    if unit is None:
        return []
    today = today or timezone.localdate()
    scope = {"unit": unit}
    sections = (
        _section("مدیریت و پروژه",
            _metric(user, "enterprise_portal.view_worktask", "کارهای باز",
                WorkTask.objects.filter(**scope).exclude(status="done")),
            _metric(user, "enterprise_portal.view_managementproject", "پروژه‌های فعال",
                ManagementProject.objects.filter(**scope, status="active"))),
        _section("حسابداری و تجارت",
            _metric(user, "enterprise_portal.view_journalentry", "اسناد حسابداری پیش‌نویس",
                JournalEntry.objects.filter(**scope, status="draft")),
            _metric(user, "enterprise_portal.view_commercialdocument", "اسناد تجاری باز",
                CommercialDocument.objects.filter(**scope).exclude(status__in=("settled", "cancelled")))),
        _section("کارخانه داخلی زمرد ملل",
            _metric(user, "ecosystem_hub.view_productionorder", "سفارش‌های برنامه‌ریزی تولید",
                ProductionOrder.objects.filter(**scope).exclude(state__in=("closed", "cancelled"))),
            _metric(user, "ecosystem_hub.view_qualityinspection", "بازرسی‌های رد یا توقف",
                QualityInspection.objects.filter(**scope, result__in=("fail", "hold"))),
            _metric(user, "ecosystem_hub.view_procurementneed", "درخواست‌های تأمین پیش‌نویس",
                ProcurementNeed.objects.filter(**scope, status__in=("draft", "review")))),
        _section("بازاریابی و فروش",
            _metric(user, "company_marketing.view_campaign", "کمپین‌های فعال",
                Campaign.objects.filter(**scope, status="active")),
            _metric(user, "company_marketing.view_lead", "سرنخ‌های باز",
                Lead.objects.filter(**scope).exclude(stage__in=("won", "lost"))),
            _metric(user, "company_marketing.view_publication", "انتشارهای تأییدشده در صف",
                Publication.objects.filter(campaign__unit=unit, status="approved"))),
        _section("پیام‌رسانی",
            _metric(user, "company_messaging.view_message", "پیام‌های منتظر ارسال",
                Message.objects.filter(**scope, status="queued")),
            _metric(user, "company_messaging.view_message", "پیام‌های مسدود یا نامشخص",
                Message.objects.filter(**scope, status__in=("blocked", "uncertain")))),
        _section("ایجنت‌ها و چرخه‌ها",
            _metric(user, "ecosystem_hub.view_assistantrun", "گزارش‌های منتظر بررسی",
                AssistantRun.objects.filter(**scope, state__in=("draft", "review"))),
            _metric(user, "ecosystem_hub.view_proposedautomation", "برنامه‌های پیشنهادی فعال",
                ProposedAutomation.objects.filter(**scope, active=True))),
        _section("تقویم و موعدهای عقب‌افتاده",
            _metric(user, "enterprise_portal.view_worktask", "کارهای عقب‌افتاده",
                WorkTask.objects.filter(**scope, due_on__lt=today).exclude(status="done")),
            _metric(user, "ecosystem_hub.view_productionorder", "سفارش‌های تولید معوق",
                ProductionOrder.objects.filter(**scope, due_date__lt=today).exclude(state__in=("closed", "cancelled")))),
    )
    return [section for section in sections if section is not None]


@never_cache
@office_access
@require_GET
def overview(request):
    require_hub(request)
    unit, units = select_unit(request)
    return page(request, "unified", {
        "selected_unit": unit,
        "units": units,
        "sections": snapshot_for_unit(request.user, unit),
        "section": "unified",
        "worker_verified": False,
        "factory_executed": False,
    })
