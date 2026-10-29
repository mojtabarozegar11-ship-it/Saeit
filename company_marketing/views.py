from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from ecosystem_hub.access import user_units, require_unit
from enterprise_portal.views import office_access, no_cache
from .forms import CampaignForm, PublicationForm, ChannelAccountForm, LeadForm, PerformanceMetricForm
from .models import Campaign, ChannelAccount, Publication, Lead, PerformanceMetric
from .services import approve_publication


def require_perm(user, code):
    if not (user.is_superuser or user.has_perm("company_marketing." + code)):
        raise PermissionDenied("مجوز بازاریابی موجود نیست.")


def visible_publications(user):
    return Publication.objects.select_related("campaign", "channel", "created_by").filter(
        campaign__unit__in=user_units(user)
    )


@office_access
@require_GET
def dashboard(request):
    require_perm(request.user, "view_campaign")
    units = user_units(request.user)
    campaigns = Campaign.objects.filter(unit__in=units)
    pubs = visible_publications(request.user)
    leads = Lead.objects.filter(unit__in=units)
    metrics = PerformanceMetric.objects.filter(publication__campaign__unit__in=units)
    return no_cache(render(request, "company_marketing/dashboard.html", {
        "campaigns": campaigns[:80], "publications": pubs[:100],
        "accounts": ChannelAccount.objects.filter(unit__in=units)[:100],
        "lead_count": leads.count(),
        "verified_sale_irr": leads.filter(stage="won").aggregate(v=Sum("verified_sale_irr"))["v"] or 0,
        "recorded_cost_irr": metrics.aggregate(v=Sum("cost_irr"))["v"] or 0,
        "can_add_campaign": request.user.is_superuser or request.user.has_perm("company_marketing.add_campaign"),
        "can_add_publication": request.user.is_superuser or request.user.has_perm("company_marketing.add_publication"),
        "can_add_channel": request.user.is_superuser or request.user.has_perm("company_marketing.add_channelaccount"),
        "can_add_lead": request.user.is_superuser or request.user.has_perm("company_marketing.add_lead"),
        "can_add_metric": request.user.is_superuser or request.user.has_perm("company_marketing.add_performancemetric"),
        "can_manage_campaigns": request.user.is_superuser or request.user.has_perm("company_marketing.manage_company_campaigns"),
        "can_verify_channel": request.user.is_superuser,
    }))


@office_access
@require_http_methods(["GET", "POST"])
def new_campaign(request):
    require_perm(request.user, "add_campaign")
    form = CampaignForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.full_clean()
        item.save()
        return no_cache(redirect("company_marketing:dashboard"))
    return no_cache(render(request, "company_marketing/form.html", {
        "form": form, "heading": "کمپین جدید", "submit": "ثبت کمپین",
    }))


@office_access
@require_http_methods(["GET", "POST"])
def new_publication(request):
    require_perm(request.user, "add_publication")
    form = PublicationForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        if not item.scheduled_at:
            item.scheduled_at = timezone.now()
        item.full_clean()
        item.save()
        return no_cache(redirect("company_marketing:detail", pk=item.pk))
    return no_cache(render(request, "company_marketing/form.html", {
        "form": form, "heading": "محتوای تبلیغاتی جدید", "submit": "ذخیره پیش‌نویس",
    }))


@office_access
@require_GET
def detail(request, pk):
    require_perm(request.user, "view_publication")
    item = get_object_or_404(visible_publications(request.user), pk=pk)
    return no_cache(render(request, "company_marketing/detail.html", {
        "publication": item,
        "events": item.events.all()[:30],
        "can_approve": request.user.is_superuser or request.user.has_perm("company_marketing.approve_publication"),
    }))


@office_access
@require_POST
def approve(request, pk):
    require_perm(request.user, "approve_publication")
    item = get_object_or_404(visible_publications(request.user), pk=pk)
    try:
        approve_publication(item.pk, request.user)
    except ValidationError as exc:
        return no_cache(render(request, "company_marketing/detail.html", {
            "publication": item, "events": item.events.all()[:30],
            "can_approve": True, "error": exc.messages,
        }, status=400))
    return no_cache(redirect("company_marketing:detail", pk=pk))


@office_access
@require_http_methods(["GET", "POST"])
def new_channel(request):
    require_perm(request.user, "add_channelaccount")
    form = ChannelAccountForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        require_unit(request.user, item.unit, write=True)
        item.is_company_owned = False
        item.verified_at = None
        item.ownership_evidence = ""
        item.full_clean()
        item.save()
        return no_cache(redirect("company_marketing:dashboard"))
    return no_cache(render(request, "company_marketing/form.html", {
        "form": form, "heading": "ثبت حساب شبکه", "submit": "ثبت برای احراز مالکیت",
    }))


@office_access
@require_POST
def verify_channel(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied("تأیید مالکیت فقط با مدیر ارشد.")
    account = get_object_or_404(ChannelAccount.objects.filter(unit__in=user_units(request.user)), pk=pk)
    evidence = (request.POST.get("evidence") or "").strip()
    if len(evidence) < 8 or len(evidence) > 255:
        return HttpResponseBadRequest("مرجع شواهد مالکیت ۸ تا ۲۵۵ نویسه باشد.")
    account.ownership_evidence = evidence
    account.is_company_owned = True
    account.verified_at = timezone.now()
    account.full_clean()
    account.save()
    return no_cache(redirect("company_marketing:dashboard"))


@office_access
@require_http_methods(["GET", "POST"])
def new_lead(request):
    require_perm(request.user, "add_lead")
    form = LeadForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        require_unit(request.user, item.unit, write=True)
        item.owner = request.user
        item.full_clean()
        item.save()
        return no_cache(redirect("company_marketing:dashboard"))
    return no_cache(render(request, "company_marketing/form.html", {
        "form": form, "heading": "سرنخ بازاریابی", "submit": "ثبت سرنخ",
    }))


@office_access
@require_http_methods(["GET", "POST"])
def new_metric(request):
    require_perm(request.user, "add_performancemetric")
    form = PerformanceMetricForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        require_unit(request.user, item.publication.campaign.unit, write=True)
        item.recorded_by = request.user
        item.full_clean()
        item.save()
        return no_cache(redirect("company_marketing:dashboard"))
    return no_cache(render(request, "company_marketing/form.html", {
        "form": form, "heading": "ثبت آمار مستند کمپین", "submit": "ثبت شاخص عملکرد",
    }))


@office_access
@require_POST
def set_campaign_state(request, pk):
    require_perm(request.user, "manage_company_campaigns")
    item = get_object_or_404(Campaign.objects.filter(unit__in=user_units(request.user)), pk=pk)
    require_unit(request.user, item.unit, write=True)
    new_state = request.POST.get("status")
    allowed = {
        "draft": ("active", "closed"),
        "active": ("paused", "closed"),
        "paused": ("active", "closed"),
        "closed": (),
    }
    if new_state not in allowed[item.status]:
        return HttpResponseBadRequest("تغییر وضعیت کمپین مجاز نیست.")
    item.status = new_state
    item.full_clean()
    item.save(update_fields=["status"])
    return no_cache(redirect("company_marketing:dashboard"))
