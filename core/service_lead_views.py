"""Consent-based, nonbinding service inquiry funnel for Zomorod Melal.

Public web forms are limited to the company site.  An accepted inquiry is NOT
an order, offer acceptance, price approval, or a claim of available capacity.
No outgoing SMS/email, network calls, payment, background task, or agents.
"""
from __future__ import annotations

import re
from datetime import timedelta

from django import forms
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.http.request import RawPostDataException
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .company_inquiry_models import CompanyInquiry
from .service_sales_controls import service_card
from .service_intake_routing import (
    LEGACY_INQUIRY_PATH, django_service_intake_active,
)

MAX_POST_BYTES = 24_576
_DUPLICATE_WINDOW = timedelta(minutes=15)
_COMPANY_HOSTS = frozenset({"zomorodmelal.ir", "www.zomorodmelal.ir"})
_TEST_HOSTS = frozenset({"testserver", "localhost", "127.0.0.1"})
_SERVICE_KIND = {
    "AGR-01": "project",
    "RS-01": "research",
    "RS-02": "research",
    "RS-03": "research",
    "WEB-01": "commercial",
    "SEO-01": "commercial",
}
_SUBMISSION_SESSION_PREFIX = "service_inquiry_received_v1_"


class ServiceLeadForm(forms.Form):
    """User-owned lead details; do not store without explicit processing consent."""

    name = forms.CharField(label="نام و نام خانوادگی", min_length=2, max_length=180)
    organization = forms.CharField(label="شرکت یا مجموعه", required=False, max_length=200)
    email = forms.EmailField(label="ایمیل پاسخگویی", max_length=254)
    phone = forms.CharField(label="شماره تماس (اختیاری)", required=False, max_length=45)
    subject = forms.CharField(label="موضوع درخواست", min_length=5, max_length=200)
    message = forms.CharField(
        label="توضیح مسئله و هدف", min_length=20, max_length=3500,
        widget=forms.Textarea(attrs={"rows": 6, "autocomplete": "off"}),
    )
    consent = forms.BooleanField(
        label="با ثبت و بررسی اطلاعات این درخواست برای پاسخ کارشناسی موافقم.",
        required=True,
    )
    website = forms.CharField(
        required=False, max_length=120, widget=forms.HiddenInput,
    )

    def clean_email(self):
        # DNS/provider verification is outside this form's control.
        return self.cleaned_data["email"].strip().lower()

    def clean_website(self):
        # Honeypot: untrusted bots should not silently generate CRM leads.
        if self.cleaned_data["website"].strip():
            raise forms.ValidationError("درخواست قابل ثبت نیست.")
        return ""

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("نام معتبر لازم است.")
        return name

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 20:
            raise forms.ValidationError("توضیح حداقل ۲۰ نویسه لازم دارد.")
        return message


def _no_cache(response):
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _request_size_allowed(request):
    length = request.META.get("CONTENT_LENGTH", "")
    if length not in ("", None):
        if not isinstance(length, str) or not re.fullmatch(r"[0-9]{1,12}", length):
            return False
        if int(length) > MAX_POST_BYTES:
            return False
        # Django's CSRF middleware may already have parsed a multipart
        # stream; re-reading .body in that case raises RawPostDataException.
        cached = getattr(request, "_body", None)
        return cached is None or len(cached) <= MAX_POST_BYTES
    # Missing or malformed transfer length: fail closed if the CSRF/form
    # parser already consumed the underlying request stream.
    try:
        return len(request.body) <= MAX_POST_BYTES
    except RawPostDataException:
        return False


def _host_allowed(request):
    host = request.get_host().split(":")[0].lower()
    return host in _COMPANY_HOSTS or (settings.DEBUG and host in _TEST_HOSTS)


def _already_recorded(*, service_code, email, subject, message, now):
    """Suppress an exact 15-min duplicate; no invoice or email is generated."""
    return CompanyInquiry.objects.filter(
        kind=_SERVICE_KIND[service_code],
        email__iexact=email,
        subject=subject,
        message=message,
        created_at__gte=now - _DUPLICATE_WINDOW,
        created_at__lte=now,
    ).exists()


@csrf_protect
@require_http_methods(["GET", "POST"])
def service_inquiry(request, service_code):
    if not _host_allowed(request):
        raise Http404("Service page belongs to Zomorod Melal")
    try:
        offer = service_card(service_code)
    except ValueError as exc:
        raise Http404("Unknown service code") from exc
    # Fail closed if PHP is still the sole routed source. GET can navigate
    # to legacy. POST MUST NOT forward form contents or cookies cross-stack.
    if not django_service_intake_active():
        if request.method == "GET":
            return _no_cache(redirect(LEGACY_INQUIRY_PATH))
        response = _no_cache(HttpResponse(
            "این مسیر فعلاً پذیرش درخواست ندارد؛ فرم اصلی خدمات را باز کنید.",
            status=503,
        ))
        response["Retry-After"] = "3600"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    session_key = _SUBMISSION_SESSION_PREFIX + service_code
    if request.method == "POST":
        if not _request_size_allowed(request):
            return _no_cache(HttpResponseBadRequest("درخواست بیش از حد مجاز است."))
        if request.content_type not in (
            "application/x-www-form-urlencoded", "multipart/form-data"
        ):
            return _no_cache(HttpResponse("فرمت فرم نامعتبر است.", status=415))
        if request.FILES:
            return _no_cache(HttpResponseBadRequest(
                "بارگذاری پرونده در این فرم پشتیبانی نمی‌شود."
            ))
        form = ServiceLeadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            subject = f"[{service_code}] {cd['subject']}"
            now = timezone.now()
            if not _already_recorded(
                service_code=service_code, email=cd["email"],
                subject=subject, message=cd["message"], now=now
            ):
                CompanyInquiry.objects.create(
                    kind=_SERVICE_KIND[service_code],
                    name=cd["name"],
                    organization=cd["organization"],
                    email=cd["email"],
                    phone=cd["phone"],
                    subject=subject,
                    message=cd["message"],
                    status="new",
                    internal_note=(
                        "Source: company service inquiry; "
                        "consent: checked; privacy_notice: service-v1; "
                        "nonbinding: true; automatic_contact: false."
                    ),
                )
            # PRG: session proof ensures '?submitted=1' never fabricates receipt.
            request.session[session_key] = True
            return _no_cache(redirect("service_inquiry", service_code=service_code))
    else:
        form = ServiceLeadForm()

    was_recorded = bool(request.session.pop(session_key, False))
    return _no_cache(render(
        request, "core/service_inquiry.html",
        {"offer": offer, "form": form, "received": was_recorded},
    ))
