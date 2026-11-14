"""Native company inquiry intake: one existing CRM, one mojtaba.bot.ai.

No email, charges, trade, LLM call, sender automation, or promise of response.
An accepted request is an internal unqualified inquiry, NOT a verified sale.
"""
from __future__ import annotations

import hashlib
import re
from datetime import timedelta

from django import forms
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from .company_inquiry_models import CompanyInquiry
from .models import AuditLog

COMPANY_HOSTS = frozenset({"zomorodmelal.ir", "www.zomorodmelal.ir"})
FORM_VERSION = "2026-11-14-consent-v1"
MAX_BODY_BYTES = 14000
MAX_SAME_EMAIL_PER_HOUR = 3
PUBLIC_CATEGORIES = dict(CompanyInquiry.KIND_CHOICES)
PLACEHOLDER_DOMAINS = frozenset({"localhost", "invalid", "test", "local"})
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WEB_LINK = re.compile(r"https?://", re.I)


def require_company_host(request):
    host = request.get_host().split(":", 1)[0].lower()
    if host in COMPANY_HOSTS:
        return
    if settings.DEBUG and host in {"testserver", "localhost", "127.0.0.1"}:
        return
    raise Http404("Company-only request channel")


class CompanySalesInquiryForm(forms.ModelForm):
    """Every new inbound lead must have a relevant purpose and explicit consent."""

    consent = forms.BooleanField(
        required=True,
        label="با ثبت اطلاعات برای بررسی همین درخواست و تماس درباره آن موافقم.",
    )
    website = forms.CharField(
        required=False, max_length=200,
        widget=forms.HiddenInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
        label="برای کاربران عادی خالی بماند",
    )
    message = forms.CharField(
        min_length=20, max_length=5000, strip=True,
        widget=forms.Textarea(attrs={"rows": 6}),
        label="شرح درخواست",
    )

    class Meta:
        model = CompanyInquiry
        fields = (
            "kind", "name", "organization", "email", "phone", "subject", "message",
        )
        labels = {
            "kind": "نوع همکاری",
            "name": "نام و نام خانوادگی",
            "organization": "سازمان / مجموعه",
            "email": "نشانی ایمیل",
            "phone": "شماره تماس (اختیاری)",
            "subject": "موضوع",
        }
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": "200"}),
            "organization": forms.TextInput(attrs={"maxlength": "250"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"maxlength": "50"}),
            "subject": forms.TextInput(attrs={"maxlength": "300"}),
        }

    def _clean_safe_text(self, key, *, minimum=1):
        value = self.cleaned_data.get(key, "")
        if type(value) is not str:
            raise forms.ValidationError("مقدار نامعتبر است.")
        value = value.strip()
        if len(value) < minimum or CONTROL.search(value):
            raise forms.ValidationError("متن معتبر نیست.")
        return value

    def clean_name(self):
        value = self._clean_safe_text("name", minimum=2)
        if "\n" in value or "\r" in value:
            raise forms.ValidationError("نام باید یک خط باشد.")
        return value

    def clean_organization(self):
        value = self._clean_safe_text("organization", minimum=0)
        if "\n" in value or "\r" in value:
            raise forms.ValidationError("سازمان باید یک خط باشد.")
        return value

    def clean_subject(self):
        value = self._clean_safe_text("subject", minimum=5)
        if "\n" in value or "\r" in value:
            raise forms.ValidationError("موضوع باید یک خط باشد.")
        return value

    def clean_email(self):
        value = self._clean_safe_text("email", minimum=6)
        if not value.isascii() or "\r" in value or "\n" in value:
            raise forms.ValidationError("ایمیل نامعتبر است.")
        local, sep, domain = value.rpartition("@")
        if (not sep or not local or not domain
                or domain.casefold() in PLACEHOLDER_DOMAINS
                or domain.casefold().endswith((".invalid", ".test", ".localhost", ".local"))):
            raise forms.ValidationError("ایمیل نامعتبر است.")
        return local + "@" + domain.casefold()

    def clean_phone(self):
        value = self._clean_safe_text("phone", minimum=0)
        if value and (not re.fullmatch(r"[+0-9() \-]{7,50}", value)
                      or len(re.sub(r"\D", "", value)) < 7):
            raise forms.ValidationError("شماره تماس نامعتبر است.")
        return value

    def clean_message(self):
        value = self._clean_safe_text("message", minimum=20)
        if len(WEB_LINK.findall(value)) > 2:
            raise forms.ValidationError("لینک‌های غیرضروری را حذف کنید.")
        return value

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("فرم نامعتبر است.")
        return ""

    def clean(self):
        data = super().clean()
        email = data.get("email")
        kind = data.get("kind")
        subject = data.get("subject")
        message = data.get("message")
        if not all((email, kind, subject, message)) or data.get("consent") is not True:
            return data
        last_hour = timezone.now() - timedelta(hours=1)
        count = CompanyInquiry.objects.filter(
            email__iexact=email, created_at__gte=last_hour,
        ).count()
        if count >= MAX_SAME_EMAIL_PER_HOUR:
            raise forms.ValidationError(
                "تعداد درخواست‌های اخیر این نشانی به سقف رسیده است."
            )
        prior = CompanyInquiry.objects.filter(
            email__iexact=email, kind=kind, subject=subject,
            message=message, created_at__gte=timezone.now() - timedelta(days=1),
        ).exists()
        if prior:
            raise forms.ValidationError(
                "این درخواست پیش‌تر دریافت شده است. برای جلوگیری از ثبت تکراری آن را دوباره نفرستید."
            )
        return data


def validate_body_size(request):
    """Refuse oversize application payloads before parsing or saving any PII."""
    try:
        n = int(request.META.get("CONTENT_LENGTH") or "0")
    except (TypeError, ValueError):
        raise forms.ValidationError("حجم درخواست نامعتبر است.")
    if n < 0 or n > MAX_BODY_BYTES:
        raise forms.ValidationError("حجم درخواست بیش از حد مجاز است.")


@transaction.atomic
def save_inbound_inquiry(form: CompanySalesInquiryForm):
    """Persist only form-approved fields. Existing CRM remains single source."""
    if not form.is_valid():
        raise ValueError("INVALID_CUSTOMER_INQUIRY")
    inquiry = form.save(commit=False)
    # A public inquiry may NEVER create a paid order, an approved deal, or
    # a payment instruction; those require separate commercial verification.
    inquiry.status = "new"
    inquiry.internal_note = ""
    inquiry.save()
    return inquiry
