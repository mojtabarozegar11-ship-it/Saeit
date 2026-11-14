"""Private CRM review and nonbinding quote drafts for the single mojtaba.bot.ai.

Source of truth: the existing CompanyInquiry and AuditLog tables. No new
customer identity, CRM, payment model, migration or second autonomous bot.
No email, live offer, order, acceptance, settlement or service delivery.
"""
from __future__ import annotations

import secrets
from decimal import Decimal
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .chat_operation_security import is_authorized_chat_operator
from .company_inquiry_models import CompanyInquiry
from .models import AuditLog

REVIEW_ACTION = "company_inquiry_reviewed"
DRAFT_ACTION = "company_nonbinding_quote_draft"
REVIEW_QUALIFICATIONS = (
    ("eligible", "نیاز برای تهیه پیش‌نویس داخلی مناسب است"),
    ("needs_details", "اطلاعات کافی نیست؛ پیگیری فقط با مجوز"),
    ("out_of_scope", "خارج از محدوده خدمات؛ بستن پرونده"),
)
SERVICE_BY_KIND = {
    "research": (
        ("agri_research_scope", "ارزیابی دامنه پژوهش کاربردی کشاورزی"),
        ("scientific_evidence_review", "مرور شواهد و منابع علمی"),
    ),
    "technology": (
        ("farm_tech_assessment", "ارزیابی امکان‌پذیری فناوری مزرعه"),
        ("agri_digital_process", "تحلیل فرایند دیجیتال کشاورزی"),
    ),
    "project": (
        ("greenhouse_feasibility", "مطالعه امکان‌سنجی گلخانه"),
        ("water_productivity_assessment", "ارزیابی بهره‌وری آب کشاورزی"),
    ),
    "commercial": (
        ("farm_economic_advisory", "مشاوره اقتصاد و مدیریت تولید کشاورزی"),
        ("supply_chain_economics", "مطالعه اقتصاد زنجیره تأمین کشاورزی"),
    ),
    "media": (
        ("scientific_content_review", "ارزیابی محتوای تخصصی و علمی"),
        ("agri_brand_content_scope", "بررسی دامنه محتوای برند کشاورزی"),
    ),
}
SERVICE_CODES = dict(choice for choices in SERVICE_BY_KIND.values() for choice in choices)
SERVICE_CHOICES = tuple(item for choices in SERVICE_BY_KIND.values() for item in choices)
CURRENCIES = (("IRT", "تومان"), ("IRR", "ریال ایران"), ("USD", "دلار آمریکا، صرفاً برآورد داخلی"))
MAX_TOTAL = Decimal("100000000000.00")
MAX_POST_BYTES = 4096
DRAFT_SCHEMA = "saeit.sales.nonbinding-internal-quote.v1"


def new_desk_token():
    return secrets.token_hex(16)


class _VersionedActionForm(forms.Form):
    def __init__(self, *args, case_kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        if case_kind is not None and "service_code" in self.fields:
            self.fields["service_code"].choices = SERVICE_BY_KIND.get(case_kind, ())

    request_token = forms.RegexField(
        regex=r"^[0-9a-f]{32}$", min_length=32, max_length=32,
        widget=forms.HiddenInput,
    )
    revision = forms.CharField(max_length=45, widget=forms.HiddenInput)

    def clean_revision(self):
        value = self.cleaned_data["revision"]
        if len(value) < 19 or "T" not in value or ("+" not in value and "Z" not in value):
            raise forms.ValidationError("INQUIRY_REVISION_INVALID")
        return value


class CompanyReviewForm(_VersionedActionForm):
    qualification = forms.ChoiceField(choices=REVIEW_QUALIFICATIONS)
    service_code = forms.ChoiceField(choices=SERVICE_CHOICES)


class CompanyDraftQuoteForm(_VersionedActionForm):
    service_code = forms.ChoiceField(choices=SERVICE_CHOICES)
    currency = forms.ChoiceField(choices=CURRENCIES)
    unit_price = forms.DecimalField(
        max_digits=12, decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("9999999999.99"),
    )
    quantity = forms.IntegerField(min_value=1, max_value=12)
    turnaround_days = forms.IntegerField(min_value=1, max_value=180)
    valid_days = forms.IntegerField(min_value=1, max_value=30)


def _require_owner(owner):
    if not is_authorized_chat_operator(owner):
        raise PermissionDenied("ACTIVE_OWNER_REQUIRED")


def _case_id(case_id):
    if type(case_id) is not int or case_id < 1:
        raise ValidationError("INVALID_CASE_IDENTIFIER")
    return case_id


def _consent_record(case_id):
    return AuditLog.objects.filter(
        action="company_inquiry_consent_submitted",
        target_type="CompanyInquiry",
        target_id=str(case_id),
    ).order_by("-pk").first()


def _case_events(case_id, action):
    return AuditLog.objects.filter(
        action=action, target_type="CompanyInquiry",
        target_id=str(case_id),
    ).order_by("-created_at", "-pk")


def _enforce_request(form):
    if not form.is_valid():
        raise ValidationError("INVALID_OWNER_ACTION_FORM")


def _context(inquiry, form, *, action):
    code = form.cleaned_data["service_code"]
    if code not in dict(SERVICE_BY_KIND.get(inquiry.kind, ())):
        raise ValidationError("SERVICE_NOT_IN_REQUEST_CATEGORY")
    consent = _consent_record(inquiry.pk)
    if not consent or consent.after_state.get("consent_checked") is not True:
        raise ValidationError("CASE_HAS_NO_CONSENT_EVIDENCE")
    trace = f"sales-{action}-{inquiry.pk}-{form.cleaned_data['request_token']}"
    if len(trace) > 100:
        raise ValidationError("ACTION_TRACE_TOO_LONG")
    return trace


def _assert_revision(inquiry, form):
    if inquiry.updated_at.isoformat() != form.cleaned_data["revision"]:
        raise ValidationError("STALE_CASE_RELOAD_REQUIRED")


def _existing(trace, *, action, inquiry_id):
    return AuditLog.objects.filter(
        trace_id=trace, action=action, target_type="CompanyInquiry",
        target_id=str(inquiry_id),
    ).order_by("pk").first()


@transaction.atomic
def review_company_inquiry(*, case_id, owner, form: CompanyReviewForm):
    """Owner-confirmed internal qualification, never contact or deal approval."""
    _require_owner(owner)
    _enforce_request(form)
    inquiry = CompanyInquiry.objects.select_for_update().get(pk=_case_id(case_id))
    trace = _context(inquiry, form, action="review")
    existing = _existing(trace, action=REVIEW_ACTION, inquiry_id=inquiry.pk)
    if existing is not None:
        return existing
    if inquiry.status not in {"new", "reviewing"}:
        raise ValidationError("CASE_NOT_OPEN_FOR_INTERNAL_QUOTE")
    _assert_revision(inquiry, form)
    before = {"status": inquiry.status}
    qualification = form.cleaned_data["qualification"]
    inquiry.status = "closed" if qualification == "out_of_scope" else "reviewing"
    inquiry.save(update_fields=["status", "updated_at"])
    return AuditLog.objects.create(
        actor_type="owner", actor_id=str(owner.pk),
        action=REVIEW_ACTION, target_type="CompanyInquiry",
        target_id=str(inquiry.pk), trace_id=trace,
        before_state=before,
        after_state={
            "status": inquiry.status,
            "qualification": qualification,
            "service_code": form.cleaned_data["service_code"],
            "reviewed_inquiry_version": inquiry.updated_at.isoformat(),
            "customer_contacted": False,
            "quote_dispatched": False,
            "legal_offer_accepted": False,
            "payment_collected": False,
        },
    )


@transaction.atomic
def prepare_internal_quote(*, case_id, owner, form: CompanyDraftQuoteForm):
    """Materialize a priced draft only after a current, consent-backed review."""
    _require_owner(owner)
    _enforce_request(form)
    inquiry = CompanyInquiry.objects.select_for_update().get(pk=_case_id(case_id))
    trace = _context(inquiry, form, action="quote")
    existing = _existing(trace, action=DRAFT_ACTION, inquiry_id=inquiry.pk)
    if existing is not None:
        return existing
    if inquiry.status not in {"new", "reviewing"}:
        raise ValidationError("CASE_NOT_OPEN_FOR_INTERNAL_QUOTE")
    _assert_revision(inquiry, form)
    if inquiry.status != "reviewing":
        raise ValidationError("QUOTE_REQUIRES_REVIEWING_STATE")
    review = _case_events(inquiry.pk, REVIEW_ACTION).first()
    if not review or review.after_state.get("qualification") != "eligible":
        raise ValidationError("QUOTE_REQUIRES_ELIGIBLE_OWNER_REVIEW")
    if review.after_state.get("service_code") != form.cleaned_data["service_code"]:
        raise ValidationError("SERVICE_NOT_OWNER_REVIEWED")
    if review.after_state.get("reviewed_inquiry_version") != inquiry.updated_at.isoformat():
        raise ValidationError("REVIEW_STALE_AFTER_CASE_CHANGE")
    quantity = form.cleaned_data["quantity"]
    unit_price = form.cleaned_data["unit_price"]
    total = quantity * unit_price
    if not total.is_finite() or total <= 0 or total > MAX_TOTAL:
        raise ValidationError("QUOTE_AMOUNT_OUTSIDE_INTERNAL_RANGE")
    return AuditLog.objects.create(
        actor_type="owner", actor_id=str(owner.pk),
        action=DRAFT_ACTION, target_type="CompanyInquiry",
        target_id=str(inquiry.pk), trace_id=trace,
        before_state={"status": "reviewing"},
        after_state={
            "schema": DRAFT_SCHEMA,
            "scope_code": form.cleaned_data["service_code"],
            "currency": form.cleaned_data["currency"],
            "quantity": quantity,
            "unit_price": str(unit_price),
            "gross_total": str(total),
            "turnaround_days": form.cleaned_data["turnaround_days"],
            "valid_days": form.cleaned_data["valid_days"],
            "status": "internal_draft",
            "customer_delivery_authorized": False,
            "customer_contacted": False,
            "legal_offer_accepted": False,
            "invoice_issued": False,
            "settlement_verified": False,
            "cash_collected": None,
            "private_and_nonbinding": True,
            "source_inquiry_version": inquiry.updated_at.isoformat(),
            "prepared_at_utc": timezone.now().isoformat(),
        },
    )


def case_drafts(case_id):
    return tuple(_case_events(_case_id(case_id), DRAFT_ACTION)[:30])


def make_review_form(inquiry):
    return CompanyReviewForm(case_kind=inquiry.kind, initial={
        "request_token": new_desk_token(),
        "revision": inquiry.updated_at.isoformat(),
        "service_code": SERVICE_BY_KIND.get(inquiry.kind, (("", ""),))[0][0],
    })


def make_quote_form(inquiry):
    latest = _case_events(inquiry.pk, REVIEW_ACTION).first()
    service = latest.after_state.get("service_code") if latest else ""
    return CompanyDraftQuoteForm(initial={
        "request_token": new_desk_token(),
        "revision": inquiry.updated_at.isoformat(),
        "service_code": service if service in SERVICE_CODES else "",
        "currency": "IRT",
        "quantity": 1,
        "valid_days": 7,
        "turnaround_days": 30,
    })
