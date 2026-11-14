"""Nonbinding, consent-aware service response drafts for the existing Mojtaba bot.

A draft helps staff act on a real inquiry; it is not a price quotation,
contract, accepted order, customer delivery, or evidence of settled funds.
Never send customer messages, create invoices, publish content or use networks.
"""
from __future__ import annotations

from hashlib import sha256
import re

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .company_inquiry_models import CompanyInquiry
from .models import AuditLog
from .service_sales_controls import SERVICE_CARDS, service_card

BOT_ID = "mojtaba.bot.ai"
SOURCE_MARKER = (
    "Source: company service inquiry; consent: checked; "
    "privacy_notice: service-v1; nonbinding: true; automatic_contact: false."
)
DRAFT_MARKER = "[mojtaba.bot.ai:service_response_draft:v1]"
MAX_NOTE_CHARS = 12_000
MAX_MESSAGE_CHARS = 3_500
MAX_NAME_CHARS = 180
MAX_SUBJECT_CHARS = 200
MAX_BATCH = 20
# Bound a single read to avoid costly full CRM scans while looking past the
# initial incomplete records. The old first-20 truncation could starve a later
# eligible customer indefinitely.
MAX_SCAN = 500
KIND_BY_CODE = {
    "AGR-01": "project",
    "RS-01": "research",
    "RS-02": "research",
    "RS-03": "research",
    "WEB-01": "commercial",
    "SEO-01": "commercial",
}
SERVICE_HEADER = re.compile(r"^\[([A-Z]{2,3}-[0-9]{2})\] ([^\n\r]+)$")


def _allowed_source(row) -> bool:
    # Only consented C04 company forms; never import unverified historical
    # email contacts, old PHP leads, or third-party databases.
    note = row.internal_note
    return isinstance(note, str) and note.startswith(SOURCE_MARKER)


def _code_for(row) -> str | None:
    match = SERVICE_HEADER.fullmatch(row.subject or "")
    if not match:
        return None
    code = match.group(1)
    if code not in SERVICE_CARDS or KIND_BY_CODE.get(code) != row.kind:
        return None
    return code


def _eligible(row) -> str:
    if row.status != "new":
        return "not_new"
    if not _allowed_source(row):
        return "consent_or_source_unverified"
    if DRAFT_MARKER in row.internal_note:
        return "already_prepared"
    code = _code_for(row)
    if code is None:
        return "unknown_or_mismatched_service"
    if not isinstance(row.name, str) or not 2 <= len(row.name.strip()) <= MAX_NAME_CHARS:
        return "invalid_name"
    if not isinstance(row.message, str) or not 20 <= len(row.message.strip()) <= MAX_MESSAGE_CHARS:
        return "invalid_message"
    if not isinstance(row.subject, str) or len(row.subject) > MAX_SUBJECT_CHARS + 9:
        return "invalid_subject"
    if not isinstance(row.email, str):
        return "invalid_contact"
    try:
        validate_email(row.email)
    except ValidationError:
        return "invalid_contact"
    if len(row.internal_note) > MAX_NOTE_CHARS - 2000:
        return "internal_note_capacity_exhausted"
    return "eligible"


def _fingerprint(row) -> str:
    # Bind the internal draft to its actual request without copying
    # untrusted name/email/message/phone into task logs or GitHub.
    pieces = (
        str(row.pk), row.kind, row.subject, row.message,
        row.email.strip().casefold(), row.name.strip(),
    )
    return sha256("\0".join(pieces).encode("utf-8")).hexdigest()


def render_internal_draft(row) -> str:
    """Useful scoped internal proposal, never an authorized customer quote."""
    code = _code_for(row)
    if code is None:
        raise ValueError("service_identifier_invalid")
    offer = service_card(code)
    deliverables = "\n".join(
        f"- {item}" for item in offer["deliverables"]
    )
    digest = _fingerprint(row)
    return (
        f"{DRAFT_MARKER}\n"
        f"bot={BOT_ID}; inquiry_id={row.pk}; service_code={code}; "
        f"request_sha256={digest}\n"
        "وضعیت: پیش‌نویس داخلی بررسی درخواست؛ فقط برای بازبینی کارشناس و مدیر.\n"
        f"خدمت: {offer['title_fa']}\n"
        "مسئله و اطلاعات مشتری: فقط در رکورد اصلی CRM مشاهده شود؛ "
        "هیچ داده شخصی در این پیش‌نویس تکرار نشود.\n"
        f"داده و مدارک موردنیاز: {offer['input']}\n"
        "خروجی‌های پیشنهادی مشروط به تأیید دامنه کار:\n"
        f"{deliverables}\n"
        f"محدودیت علمی/عملیاتی: {offer['limitation']}\n"
        "گیت دامنه و تحویل: نیازمند ارزیابی منابع، ظرفیت اجرایی، "
        "حقوق داده، رضایت، معیار پذیرش و زمان‌بندی قابل اجرا.\n"
        "گیت تجاری: قیمت و ارز فقط بعد از برآورد هزینه و تأیید موردی مالک؛ "
        "بدون پیش‌فاکتور، قرارداد، لینک پرداخت، تعهد یا ادعای موجودی.\n"
        "گیت ارتباط: صرفاً آماده بررسی؛ ارسال ایمیل، تماس یا پیامک خودکار ممنوع.\n"
        "گیت پذیرش: پس از بررسی انسانی و تأیید قانونی/مالی، "
        "پیشنهاد واقعی جداگانه تنظیم شود.\n"
        "گیت شواهد: این متن اثبات سفارش، فروش، تحویل یا درآمد وصول‌شده نیست.\n"
        "[/mojtaba.bot.ai:service_response_draft:v1]"
    )


def _candidate_filter():
    # Push selection down to the database. Do not scan unrelated private CRM
    # records and never use user-provided SQL/regex or raw request payloads.
    service_q = Q(pk__in=[])
    for code, kind in KIND_BY_CODE.items():
        service_q |= Q(kind=kind, subject__startswith=f"[{code}] ")
    return (
        CompanyInquiry.objects.filter(
            status="new", internal_note__contains=SOURCE_MARKER
        )
        .filter(service_q)
        .exclude(internal_note__contains=DRAFT_MARKER)
        .order_by("created_at", "pk")
    )


def _scan_candidates():
    """Bounded, deterministic candidate review; return no private fields.

    A failed record is counted with a fixed reason code, never printed. The
    extra row distinguishes 'no buyer' from 'more queue not yet inspected'.
    """
    rows = list(_candidate_filter()[:MAX_SCAN + 1])
    limit_reached = len(rows) > MAX_SCAN
    inspected = rows[:MAX_SCAN]
    eligible_ids = []
    reasons = {}
    for row in inspected:
        state = _eligible(row)
        if state == "eligible":
            eligible_ids.append(row.pk)
        else:
            reasons[state] = reasons.get(state, 0) + 1
    return eligible_ids, reasons, len(inspected), limit_reached


def preview_candidates(limit=MAX_BATCH) -> dict:
    """Read-only lead quality census across up to MAX_SCAN candidate rows."""
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH:
        raise ValueError("invalid_batch_limit")
    eligible_ids, reasons, inspected, limited = _scan_candidates()
    return {
        "bot": BOT_ID,
        "mode": "read_only",
        "candidate_count": inspected,
        "eligible_count": min(len(eligible_ids), limit),
        "eligible_seen_in_scan": len(eligible_ids),
        "requires_human_review_count": sum(reasons.values()),
        "review_reason_counts": dict(sorted(reasons.items())),
        "scan_rows_max": MAX_SCAN,
        "scan_limit_reached": limited,
        "scan_complete": not limited,
        "customer_details_exposed": False,
        "emails_sent": 0,
        "prices_set": 0,
        "invoices_created": 0,
        "cash_receipts_verified": None,
    }


@transaction.atomic
def prepare_one(inquiry_id: int) -> dict:
    """Atomic, idempotent internal CRM action for the one canonical bot."""
    if type(inquiry_id) is not int or inquiry_id < 1:
        raise ValueError("invalid_inquiry_id")
    row = (
        CompanyInquiry.objects.select_for_update()
        .filter(pk=inquiry_id).first()
    )
    if row is None:
        return {"state": "not_found", "verified_effect": False}
    reason = _eligible(row)
    if reason != "eligible":
        return {
            "state": reason,
            "verified_effect": False,
        }
    snippet = render_internal_draft(row)
    note = row.internal_note.rstrip()
    new_note = note + "\n\n" + snippet
    if len(new_note) > MAX_NOTE_CHARS:
        return {"state": "internal_note_capacity_exhausted", "verified_effect": False}
    row.internal_note = new_note
    row.status = "reviewing"
    row.save(update_fields=("internal_note", "status", "updated_at"))
    digest = _fingerprint(row)
    AuditLog.objects.create(
        actor_type="agent",
        actor_id=BOT_ID,
        action="service_response_draft_prepared",
        target_type="CompanyInquiry",
        target_id=str(row.pk),
        trace_id=f"service-draft-{row.pk}-{digest[:20]}",
        after_state={
            "service_code": _code_for(row),
            "request_sha256_prefix": digest[:20],
            "internal_draft_prepared": True,
            "buyer_contacted": False,
            "price_approved": False,
            "cash_settled": False,
            "human_review_required": True,
        },
    )
    return {
        "state": "prepared_internal_draft",
        "verified_effect": True,
        "action_performed": "Prepared nonbinding, service-specific CRM draft for owner review.",
        "evidence": {
            "kind": "company_inquiry_internal_draft",
            "inquiry_id": row.pk,
            "request_sha256_prefix": digest[:20],
            "source": "consented_first_party_service_form",
        },
        "customer_contacted": False,
        "external_payment_received": None,
        "next_action": "owner_review_service_proposal",
    }


def prepare_next() -> dict:
    """Prepare one real lead, even behind invalid historic CRM entries.

    Do not tell the master bot there is no work when the bounded scan has not
    reached the end of the queue. A large malformed backlog needs operator
    triage, not fabricated progress or a parallel worker.
    """
    eligible_ids, reasons, inspected, limited = _scan_candidates()
    for inquiry_id in eligible_ids:
        result = prepare_one(inquiry_id)
        if result.get("verified_effect") is True:
            return result
        # Concurrent staff/bot changes can invalidate a selected row. Try
        # other already-observed eligible records rather than abandoning work.
    return {
        "state": (
            "scan_limit_reached_requires_manual_triage"
            if limited else "no_eligible_consented_service_inquiry"
        ),
        "verified_effect": False,
        "candidate_count_inspected": inspected,
        "requires_human_review_count": sum(reasons.values()),
        "scan_limit_reached": limited,
        "customer_contacted": False,
        "external_payment_received": None,
    }
