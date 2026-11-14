"""Real, atomic CRM-to-desk handoff for the one Mojtaba.bot.ai economic agent.

Produces a WorkItem in the existing command center, not a new worker,
external communication, payment instruction or accepted sales order.
An inactive, login-disabled actor records the bot as creator without
impersonating a staff user or granting system permissions.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from command_center.models import WorkItem
from .company_inquiry_models import CompanyInquiry
from .models import AuditLog
from .service_quote_draft import (
    BOT_ID, DRAFT_MARKER, SOURCE_MARKER, _code_for, _fingerprint,
)

SOURCE_TYPE = "company_service_proposal"
SERVICE_ACTOR_USERNAME = "mojtaba.bot.ai"


def _bot_service_actor():
    """Reserved non-login audit principal; never an active second bot."""
    User = get_user_model()
    actor, _ = User.objects.get_or_create(
        username=SERVICE_ACTOR_USERNAME,
        defaults={
            "email": "",
            "password": make_password(None),
            "is_active": False,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    # Creation via get_or_create bypasses create_user password hashing; refuse
    # even a theoretically usable credential and force an unusable secret.
    if (
        actor.is_active or actor.is_staff or actor.is_superuser
        or actor.has_usable_password()
    ):
        raise ValueError("bot_desk_actor_security_mismatch")
    return actor


@transaction.atomic
def handoff_prepared_inquiry(inquiry_id, *, created_by=None):
    """One scoped CRM record → one real, nonbinding owner-desk WorkItem.

    Caller must wrap draft preparation + this handoff in one outer transaction
    when both actions should commit together.
    """
    if type(inquiry_id) is not int or inquiry_id < 1:
        raise ValueError("invalid_inquiry_id")

    row = (
        CompanyInquiry.objects.select_for_update()
        .filter(pk=inquiry_id).first()
    )
    if row is None:
        return {"state": "inquiry_not_found", "verified_effect": False}
    code = _code_for(row)
    if not (
        row.status == "reviewing"
        and isinstance(row.internal_note, str)
        and row.internal_note.startswith(SOURCE_MARKER)
        and DRAFT_MARKER in row.internal_note
        and code is not None
    ):
        return {"state": "consent_scope_or_draft_unverified", "verified_effect": False}

    digest = _fingerprint(row)[:20]
    proof = AuditLog.objects.filter(
        action="service_response_draft_prepared",
        actor_type="agent",
        actor_id=BOT_ID,
        target_type="CompanyInquiry",
        target_id=str(row.pk),
        trace_id=f"service-draft-{row.pk}-{digest}",
    ).order_by("-pk").first()
    if (
        proof is None
        or not isinstance(proof.after_state, dict)
        or proof.after_state.get("request_sha256_prefix") != digest
        or proof.after_state.get("service_code") != code
    ):
        return {"state": "source_draft_audit_proof_missing", "verified_effect": False}

    existing = (
        WorkItem.objects.select_for_update().filter(
            source_type=SOURCE_TYPE, source_id=str(row.pk),
        ).order_by("pk").first()
    )
    if existing is not None:
        return {
            "state": "existing_desk_workitem",
            "verified_effect": False,
            "workitem_id": existing.pk,
            "created_new": False,
            "customer_contacted": False,
        }

    if created_by is None:
        creator = _bot_service_actor()
    else:
        User = get_user_model()
        if (
            not isinstance(created_by, User)
            or created_by.pk is None
            or not created_by.is_active
            or not created_by.is_staff
            or not created_by.has_perm("core.change_companyinquiry")
        ):
            return {"state": "creator_not_authorized", "verified_effect": False}
        creator = created_by

    item = WorkItem.objects.create(
        source_type=SOURCE_TYPE,
        source_id=str(row.pk),
        created_by=creator,
        title=f"بررسی دامنه و هزینه خدمت {code} — پرونده #{row.pk}",
        description=(
            "درخواست خدمات دارای منشأ، رضایت و سند آماده‌سازی پیش‌نویس است. "
            "برای مشاهده مشخصات مشتری فقط به پرونده اصلی CRM مراجعه شود. "
            "محدوده، امکان تحویل، مستندات داده و هزینه‌ها بررسی شوند. "
            "هر نوع قیمت، ارسال، قرارداد، پرداخت یا انتشار نیازمند تأیید جداگانه است."
        ),
        status="open",
        priority="high",
        due_at=timezone.now() + timedelta(hours=24),
    )
    return {
        "state": "desk_workitem_created",
        "verified_effect": True,
        "created_new": True,
        "workitem_id": item.pk,
        "inquiry_id": row.pk,
        "due_at": item.due_at.isoformat(),
        "actor_kind": "single_bot_inactive_audit_principal" if created_by is None else "authorized_staff",
        "customer_contacted": False,
        "price_approved": False,
        "payment_received": None,
        "next_action": "owner_review_real_desk_workitem",
    }
