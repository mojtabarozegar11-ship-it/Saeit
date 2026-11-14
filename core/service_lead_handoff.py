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

MAX_ORPHAN_SCAN = 500


def orphaned_handoff_snapshot():
    """Bounded evidence of prepared, audited leads lacking a desk WorkItem.

    Older drafts are not lost when a previous cycle completed a proposal but
    did not dispatch a task. Both queue ends get a chance; uninspected middle
    is disclosed explicitly. Customer contact fields never leave this module.
    """
    queue = CompanyInquiry.objects.filter(
        status="reviewing",
        internal_note__startswith=SOURCE_MARKER,
        internal_note__contains=DRAFT_MARKER,
    )
    total = queue.count()
    if total <= MAX_ORPHAN_SCAN:
        rows = list(queue.order_by("created_at", "pk")[:MAX_ORPHAN_SCAN])
    else:
        rows = (
            list(queue.order_by("created_at", "pk")[:MAX_ORPHAN_SCAN // 2])
            + list(queue.order_by("-created_at", "-pk")[:MAX_ORPHAN_SCAN // 2])
        )
    source_ids = [str(row.pk) for row in rows]
    existing = set(
        WorkItem.objects.filter(
            source_type=SOURCE_TYPE,
            source_id__in=source_ids,
        ).values_list("source_id", flat=True)
    )
    possible = [row for row in rows if str(row.pk) not in existing]
    proofs = AuditLog.objects.filter(
        actor_type="agent", actor_id=BOT_ID,
        action="service_response_draft_prepared",
        target_type="CompanyInquiry",
        target_id__in=[str(row.pk) for row in possible],
    ).values("target_id", "trace_id", "after_state")
    proof_keys = set()
    for proof in proofs:
        state = proof["after_state"]
        if isinstance(state, dict):
            digest = state.get("request_sha256_prefix")
            code = state.get("service_code")
            # JSON audit state can contain malformed arrays/objects from
            # legacy imports. Never hash untrusted values as tuple members.
            if isinstance(digest, str) and isinstance(code, str):
                proof_keys.add((
                    proof["target_id"],
                    proof["trace_id"],
                    digest,
                    code,
                ))
    eligible = []
    for row in possible:
        code = _code_for(row)
        if code is None:
            continue
        digest = _fingerprint(row)[:20]
        if (
            str(row.pk), f"service-draft-{row.pk}-{digest}",
            digest, code,
        ) in proof_keys:
            eligible.append(row.pk)
    return {
        "inspected": len(rows),
        "queue_total": total,
        "uninspected": max(0, total - len(rows)),
        "verified_candidate_count": len(eligible),
        "verified_inquiry_ids_internal": eligible,
        "scan_complete": total <= MAX_ORPHAN_SCAN,
        "cash_received": None,
        "customer_contacted": False,
    }


def recover_one_orphaned_handoff():
    """Restore one missing, already evidenced desk task for the existing bot."""
    inventory = orphaned_handoff_snapshot()
    for pk in inventory["verified_inquiry_ids_internal"]:
        result = handoff_prepared_inquiry(pk)
        if result.get("verified_effect") is True:
            return {
                "state": "evidenced_draft_handoff_recovered",
                "verified_effect": True,
                "action_performed": "Recovered one missing real owner-desk follow-up for an existing audited CRM scope.",
                "evidence": {
                    "kind": "company_service_proposal_recovery",
                    "inquiry_id": pk,
                    "workitem_id": result["workitem_id"],
                    "desk_handoff_verified": True,
                    "customer_contacted": False,
                    "cash_reconciled": False,
                },
                "next_action": "owner_review_real_desk_workitem",
            }
    return {
        "state": "orphan_queue_incomplete_requires_review" if not inventory["scan_complete"]
        else "no_verified_orphaned_service_handoff",
        "verified_effect": False,
        "inspected": inventory["inspected"],
        "uninspected": inventory["uninspected"],
        "customer_contacted": False,
        "cash_received": None,
    }
