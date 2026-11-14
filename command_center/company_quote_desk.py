"""Owner-only lead-to-internal-quote workbench, zero external actions."""
from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core.chat_operation_security import is_authorized_chat_operator
from core.company_inquiry_models import CompanyInquiry
from core.company_sales_intake import require_company_host
from core.company_quote_workflow import (
    MAX_POST_BYTES, CompanyReviewForm, CompanyDraftQuoteForm,
    case_drafts, make_review_form, make_quote_form,
    prepare_internal_quote, review_company_inquiry,
    SERVICE_CODES, SERVICE_BY_KIND,
)
from core.models import AuditLog


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "same-origin"
    return response


def _gate(request):
    if not is_authorized_chat_operator(getattr(request, "user", None)):
        return _private(HttpResponseForbidden("Active owner required."))
    require_company_host(request)
    return None


@never_cache
@require_GET
def sales_cases(request):
    denied = _gate(request)
    if denied is not None:
        return denied
    pages = Paginator(
        CompanyInquiry.objects.all().order_by("-created_at", "-pk"), 25
    )
    current = pages.get_page(request.GET.get("page", "1"))
    return _private(render(request, "command_center/sales_cases.html", {
        "items": current,
        "total": pages.count,
        "bot_id": "mojtaba.bot.ai",
    }))


def _detail(request, case, *, review_form=None, quote_form=None,
            error=None, status=200):
    drafts = case_drafts(case.pk)
    latest_review = AuditLog.objects.filter(
        target_type="CompanyInquiry", target_id=str(case.pk),
        action="company_inquiry_reviewed",
    ).order_by("-created_at", "-pk").first()
    return _private(render(request, "command_center/sales_case_detail.html", {
        "case": case,
        "review_form": review_form if review_form is not None else make_review_form(case),
        "quote_form": quote_form if quote_form is not None else make_quote_form(case),
        "latest_review": latest_review,
        "drafts": drafts,
        "service_names": SERVICE_CODES,
        "eligible_services": SERVICE_BY_KIND.get(case.kind, ()),
        "error": error,
        "bot_id": "mojtaba.bot.ai",
    }, status=status))


@never_cache
@require_GET
def sales_case_detail(request, case_id):
    denied = _gate(request)
    if denied is not None:
        return denied
    case = get_object_or_404(CompanyInquiry, pk=case_id)
    return _detail(request, case)


@never_cache
@csrf_protect
@require_POST
def sales_case_action(request, case_id, operation):
    denied = _gate(request)
    if denied is not None:
        return denied
    if operation not in ("review", "draft"):
        raise Http404("Unknown internal sales operation")
    case = get_object_or_404(CompanyInquiry, pk=case_id)
    try:
        length = int(request.META.get("CONTENT_LENGTH") or "0")
    except (TypeError, ValueError):
        length = -1
    if length < 0 or length > MAX_POST_BYTES:
        return _private(HttpResponse("Invalid request size", status=413))
    form = (CompanyReviewForm(request.POST, case_kind=case.kind)
            if operation == "review"
            else CompanyDraftQuoteForm(request.POST, case_kind=case.kind))
    if not form.is_valid():
        return _detail(
            request, case,
            review_form=form if operation == "review" else None,
            quote_form=form if operation == "draft" else None,
            error="داده‌های اقدام معتبر نیست؛ فیلدهای مشخص‌شده را بررسی کنید.",
            status=422,
        )
    try:
        if operation == "review":
            review_company_inquiry(
                case_id=case.pk, owner=request.user, form=form,
            )
        else:
            prepare_internal_quote(
                case_id=case.pk, owner=request.user, form=form,
            )
    except ValidationError as exc:
        code = exc.messages[0] if exc.messages else "REVIEW_REJECTED"
        return _detail(
            request, case,
            review_form=form if operation == "review" else None,
            quote_form=form if operation == "draft" else None,
            error=code, status=409,
        )
    return _private(redirect(reverse("mojtaba_company_case_detail", args=[case.pk])))
