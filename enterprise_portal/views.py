"""Login-only internal company workspace: all views scoped by Django permissions."""
from decimal import Decimal
from functools import wraps
from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .forms import CompanyAuthenticationForm, TaskForm, LetterForm, has_office_access
from .models import (
    AuditEvent, BudgetPlan, BusinessUnit, CommercialDocument, CompanyAsset,
    InventoryItem, JournalEntry, JournalLine, ManagementProject, Meeting,
    OfficeLetter, Partner, StockMovement, WorkTask,
)
from .services import stock_balance
from ecosystem_hub.access import user_units


def no_cache(response):
    response["Cache-Control"] = "private, no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Referrer-Policy"] = "same-origin"
    return response


def ensure_tls(request):
    # A finance/admin session must never be processed as cleartext outside tests.
    return settings.DEBUG or request.is_secure()


def office_access(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not ensure_tls(request):
            return no_cache(HttpResponseForbidden("ورود امن فقط از HTTPS امکان‌پذیر است."))
        if not request.user.is_authenticated:
            return no_cache(redirect_to_login(
                request.get_full_path(),
                reverse("enterprise_portal:login"),
            ))
        if not has_office_access(request.user):
            raise PermissionDenied("مجوز ورود به میزکار خصوصی شرکت موجود نیست.")
        return view(request, *args, **kwargs)
    return wrapped


def required_permission(request, code):
    if not (request.user.is_superuser or request.user.has_perm(f"enterprise_portal.{code}")):
        raise PermissionDenied("مجوز مشاهده این بخش در حساب شما فعال نیست.")


def page(request, template, context):
    return no_cache(render(request, f"enterprise_portal/{template}.html", context))


@method_decorator(never_cache, name="dispatch")
class CompanyLogin(LoginView):
    template_name = "enterprise_portal/login.html"
    authentication_form = CompanyAuthenticationForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if not ensure_tls(request):
            return no_cache(HttpResponseForbidden("ورود امن فقط از HTTPS امکان‌پذیر است."))
        return no_cache(super().dispatch(request, *args, **kwargs))

    def get_success_url(self):
        return self.get_redirect_url() or reverse("enterprise_portal:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        # Financial office sessions expire after thirty minutes.
        self.request.session.set_expiry(30 * 60)
        return no_cache(response)


class CompanyLogout(LogoutView):
    next_page = "enterprise_portal:login"

    def dispatch(self, request, *args, **kwargs):
        return no_cache(super().dispatch(request, *args, **kwargs))


MODULES = [
    {"key": "finance", "title": "حسابداری و دفتر کل", "text": "کدینگ حساب‌ها، سند دوطرفه، گزارش تراز به تفکیک ارز", "icon": "₿", "permission": "view_journalentry", "url": "enterprise_portal:finance"},
    {"key": "trade", "title": "خرید، فروش و قراردادها", "text": "طرف‌های تجاری، فاکتورها، مبلغ، سررسید و وضعیت", "icon": "◈", "permission": "view_commercialdocument", "admin": "admin:enterprise_portal_commercialdocument_changelist"},
    {"key": "stock", "title": "انبار و تولید", "text": "کالاها، ورود و خروج قطعی، موجودی و نقطه سفارش", "icon": "▣", "permission": "view_inventoryitem", "url": "enterprise_portal:inventory"},
    {"key": "office", "title": "دبیرخانه و مکاتبات", "text": "نامه‌های وارده، صادره، داخلی و محرمانه", "icon": "✉", "permission": "view_officeletter", "url": "enterprise_portal:letters"},
    {"key": "tasks", "title": "اتوماسیون وظایف", "text": "ارجاع کار، اولویت، پیگیری، سررسید و مسئولیت", "icon": "✓", "permission": "view_worktask", "url": "enterprise_portal:tasks"},
    {"key": "meetings", "title": "جلسات و صورت‌جلسات", "text": "تقویم، دستور جلسه، افراد حاضر و مصوبات", "icon": "◷", "permission": "view_meeting", "admin": "admin:enterprise_portal_meeting_changelist"},
    {"key": "projects", "title": "برنامه‌ها و پروژه‌ها", "text": "مدیریت طرح‌های صنعتی، تجاری و پژوهشی شرکت", "icon": "◇", "permission": "view_managementproject", "admin": "admin:enterprise_portal_managementproject_changelist"},
    {"key": "budgets", "title": "بودجه و برنامه مالی", "text": "اعتبار مصوب و پیشنهادی در واحدها و ارزهای جداگانه", "icon": "▤", "permission": "view_budgetplan", "admin": "admin:enterprise_portal_budgetplan_changelist"},
    {"key": "assets", "title": "اموال و دارایی ثابت", "text": "ثبت تجهیزات، محل، تاریخ خرید و مسئول نگهداری", "icon": "⬡", "permission": "view_companyasset", "admin": "admin:enterprise_portal_companyasset_changelist"},
    {"key": "audit", "title": "گزارش حسابرسی داخلی", "text": "سوابق قطعی‌سازی اسناد و گردش انبار", "icon": "≡", "permission": "view_auditevent", "admin": "admin:enterprise_portal_auditevent_changelist"},
]


@never_cache
@office_access
@require_GET
def dashboard(request):
    user = request.user
    modules = [item for item in MODULES
               if user.is_superuser or user.has_perm("enterprise_portal." + item["permission"])]
    summary = []
    if user.is_superuser or user.has_perm("enterprise_portal.view_businessunit"):
        summary.append(("واحدهای شرکت", user_units(user).filter(active=True).count()))
    if user.is_superuser or user.has_perm("enterprise_portal.view_worktask"):
        tasks = WorkTask.objects.exclude(status="done")
        if not user.is_superuser and not user.has_perm("enterprise_portal.change_worktask"):
            tasks = tasks.filter(Q(assigned_to=user) | Q(created_by=user))
        summary.append(("کارهای باز", tasks.count()))
    if user.is_superuser or user.has_perm("enterprise_portal.view_officeletter"):
        qs = _visible_letters(user)
        summary.append(("نامه‌های ثبت‌شده", qs.count()))
    if user.is_superuser or user.has_perm("enterprise_portal.view_managementproject"):
        summary.append(("پروژه‌های در اجرا", ManagementProject.objects.filter(status="active", unit__in=user_units(user)).count()))
    return page(request, "dashboard", {
        "modules": modules, "summary": summary, "section": "dashboard",
    })


def _visible_letters(user):
    qs = OfficeLetter.objects.all()
    if not user.is_superuser and not user.has_perm("enterprise_portal.view_confidential_letters"):
        qs = qs.filter(Q(classification="normal") | Q(assigned_to=user) | Q(created_by=user))
    return qs


@never_cache
@office_access
@require_GET
def finance(request):
    required_permission(request, "view_journalentry")
    totals = (
        JournalLine.objects.filter(entry__status="posted", entry__unit__in=user_units(request.user))
        .values("entry__unit__code", "entry__unit__name", "entry__currency")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("entry__unit__code", "entry__currency")
    )
    records = []
    for item in totals:
        records.append({
            "code": item["entry__unit__code"], "unit": item["entry__unit__name"],
            "currency": item["entry__currency"], "debit": item["debit"] or Decimal("0"),
            "credit": item["credit"] or Decimal("0"),
        })
    return page(request, "finance", {
        "section": "finance",
        "records": records,
        "posted_count": JournalEntry.objects.filter(status="posted", unit__in=user_units(request.user)).count(),
        "draft_count": JournalEntry.objects.filter(status="draft", unit__in=user_units(request.user)).count(),
    })



@never_cache
@office_access
@require_GET
def inventory(request):
    required_permission(request, "view_inventoryitem")
    required_permission(request, "view_stockmovement")
    products = InventoryItem.objects.select_related("unit").filter(active=True, unit__in=user_units(request.user)).order_by("unit__code", "sku")[:150]
    records = []
    for item in products:
        balance = stock_balance(item.pk)
        records.append({"item": item, "balance": balance,
                        "needs_reorder": balance <= item.reorder_point})
    return page(request, "inventory", {
        "section": "inventory", "records": records,
    })


@never_cache
@office_access
@require_GET
def tasks(request):
    required_permission(request, "view_worktask")
    qs = WorkTask.objects.select_related("assigned_to", "unit").order_by("due_on", "-created_at")
    if not request.user.is_superuser and not request.user.has_perm("enterprise_portal.change_worktask"):
        qs = qs.filter(Q(assigned_to=request.user) | Q(created_by=request.user))
    return page(request, "tasks", {
        "section": "tasks", "tasks": qs[:100],
        "can_add": request.user.has_perm("enterprise_portal.add_worktask"),
    })


@never_cache
@office_access
@require_GET
def letters(request):
    required_permission(request, "view_officeletter")
    qs = _visible_letters(request.user).select_related("assigned_to").order_by("-sent_on", "-pk")
    return page(request, "letters", {
        "section": "letters", "letters": qs[:100],
        "can_add": request.user.has_perm("enterprise_portal.add_officeletter"),
    })


@never_cache
@office_access
@require_http_methods(["GET", "POST"])
def new_task(request):
    required_permission(request, "add_worktask")
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        with transaction.atomic():
            item.save()
            AuditEvent.objects.create(actor=request.user, action="office_task_created",
                                      target=f"WorkTask:{item.pk}", detail={"title": item.title})
        return no_cache(redirect("enterprise_portal:tasks"))
    return page(request, "form", {
        "section": "tasks", "form": form, "heading": "ثبت و ارجاع کار جدید",
        "submit_label": "ثبت وظیفه", "back_url": reverse("enterprise_portal:tasks"),
    })


@never_cache
@office_access
@require_http_methods(["GET", "POST"])
def new_letter(request):
    required_permission(request, "add_officeletter")
    form = LetterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        with transaction.atomic():
            item.save()
            AuditEvent.objects.create(actor=request.user, action="office_letter_created",
                                      target=f"OfficeLetter:{item.pk}",
                                      detail={"number": item.number, "classification": item.classification})
        return no_cache(redirect("enterprise_portal:letters"))
    return page(request, "form", {
        "section": "office", "form": form, "heading": "ثبت نامه در دبیرخانه",
        "submit_label": "ثبت نامه", "back_url": reverse("enterprise_portal:letters"),
    })
