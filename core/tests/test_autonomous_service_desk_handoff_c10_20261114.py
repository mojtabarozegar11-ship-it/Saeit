"""C10: one-bot service acquisition -> scoped proposal -> real desk handoff.

The only claimed financial result is None. These tests exercise durable DB
work-items and credible provenance, not fake customer orders or payments.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.utils import timezone

from command_center.models import WorkItem
from core.company_inquiry_models import CompanyInquiry
from core.economic_tool_pack import service_proposal_prepare
from core.models import Agent, AgentTask, AuditLog, Order
from core.service_lead_handoff import (
    SERVICE_ACTOR_USERNAME, SOURCE_TYPE, handoff_prepared_inquiry,
)
from core.service_quote_draft import SOURCE_MARKER, DRAFT_MARKER, prepare_one


@pytest.fixture
def buyer(db):
    return CompanyInquiry.objects.create(
        kind="project", name="Confidential Buyer",
        email="confidential@example.invalid", phone="PRIVATE-PHONE",
        subject="[AGR-01] Operational scope review",
        message="We need a cost-and-scope review for our agricultural operations.",
        status="new",
        internal_note=SOURCE_MARKER,
    )


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_superuser(
        username="owner-c10", email="owner-c10@example.invalid",
        password="never-a-real-secret",
    )


@pytest.mark.django_db
def test_master_creates_both_actual_crm_proposal_and_durable_desk_task(buyer):
    result = service_proposal_prepare({})
    buyer.refresh_from_db()
    assert result["verified_effect"] is True
    assert result["state"] == "prepared_and_desk_handoff"
    assert result["evidence"]["inquiry_id"] == buyer.pk
    assert result["evidence"]["desk_handoff_verified"] is True
    desk = WorkItem.objects.get(source_type=SOURCE_TYPE, source_id=str(buyer.pk))
    assert desk.pk == result["evidence"]["workitem_id"]
    assert desk.status == "open"
    assert desk.priority == "high"
    assert buyer.status == "reviewing"
    assert DRAFT_MARKER in buyer.internal_note
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1


@pytest.mark.django_db
def test_bot_actor_is_nonlogin_audit_identity_not_a_second_autonomous_agent(buyer):
    before = Agent.objects.count()
    service_proposal_prepare({})
    actor = get_user_model().objects.get(username=SERVICE_ACTOR_USERNAME)
    assert actor.is_active is False
    assert actor.is_staff is False
    assert actor.is_superuser is False
    assert actor.has_usable_password() is False
    assert WorkItem.objects.get().created_by_id == actor.pk
    assert Agent.objects.count() == before


@pytest.mark.django_db
def test_service_actor_is_not_created_without_a_real_eligible_buyer(db):
    result = service_proposal_prepare({})
    assert result["verified_effect"] is False
    assert WorkItem.objects.count() == 0
    assert not get_user_model().objects.filter(username=SERVICE_ACTOR_USERNAME).exists()
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_first_party_crm_task_never_duplicates_buyer_private_data(buyer):
    receipt = service_proposal_prepare({})
    item = WorkItem.objects.get(pk=receipt["evidence"]["workitem_id"])
    text = item.title + item.description + str(item.source_id)
    for secret in (buyer.name, buyer.email, buyer.phone, buyer.message):
        assert secret not in text
    assert "AGR-01" in text
    assert "تأیید جداگانه" in text


@pytest.mark.django_db
def test_bot_desk_handoff_due_at_is_real_twenty_four_hours(buyer):
    before = timezone.now()
    service_proposal_prepare({})
    record = WorkItem.objects.get()
    assert before + timedelta(hours=23, minutes=59) < record.due_at
    assert record.due_at <= timezone.now() + timedelta(hours=24, minutes=1)


@pytest.mark.django_db
def test_one_buyer_no_duplicate_workitem_or_draft_on_second_run(buyer):
    first = service_proposal_prepare({})
    second = service_proposal_prepare({})
    assert first["verified_effect"] is True
    assert second["verified_effect"] is False
    assert WorkItem.objects.count() == 1
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1
    buyer.refresh_from_db()
    assert buyer.internal_note.count(DRAFT_MARKER) == 1


@pytest.mark.django_db
def test_auto_worker_end_to_end_generates_real_handoff_not_just_a_log(buyer):
    call_command("seed_online_income_agents", stdout=StringIO())
    initial_count = Agent.objects.count()
    call_command("online_income_cycle", stdout=StringIO())
    assert AgentTask.objects.filter(
        capability_code="income_service_proposal_prepare",
        status="queued",
    ).count() == 1
    call_command("run_economic_worker", stdout=StringIO())
    task = AgentTask.objects.get(capability_code="income_service_proposal_prepare")
    assert task.status == "completed"
    assert task.output_data["verified_effect"] is True
    assert task.output_data["evidence"]["desk_handoff_verified"] is True
    assert WorkItem.objects.get().source_id == str(buyer.pk)
    assert Agent.objects.count() == initial_count
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_worker_never_emails_or_creates_payment_during_handoff(buyer):
    with patch("django.core.mail.send_mail", side_effect=AssertionError("email forbidden")):
        service_proposal_prepare({})
    assert WorkItem.objects.count() == 1
    assert Order.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("forbidden_actor", [
    {"is_active": True, "is_staff": False, "is_superuser": False},
    {"is_active": False, "is_staff": True, "is_superuser": False},
    {"is_active": False, "is_staff": False, "is_superuser": True},
])
def test_reserved_actor_collision_causes_atomic_rollback(buyer, forbidden_actor):
    User = get_user_model()
    User.objects.create_user(
        username=SERVICE_ACTOR_USERNAME, password="test-restricted",
        **forbidden_actor,
    )
    with pytest.raises(ValueError, match="bot_desk_actor_security_mismatch"):
        service_proposal_prepare({})
    buyer.refresh_from_db()
    assert buyer.status == "new"
    assert DRAFT_MARKER not in buyer.internal_note
    assert WorkItem.objects.count() == 0
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 0


@pytest.mark.django_db
def test_inactive_actor_with_usable_password_is_not_accepted(buyer):
    get_user_model().objects.create_user(
        username=SERVICE_ACTOR_USERNAME,
        is_active=False, is_staff=False,
        password="test-restricted",
    )
    with pytest.raises(ValueError, match="bot_desk_actor_security_mismatch"):
        service_proposal_prepare({})
    buyer.refresh_from_db()
    assert buyer.status == "new"
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_worker_transaction_rolls_back_if_desk_write_fails(buyer):
    with patch(
        "core.service_lead_handoff.WorkItem.objects.create",
        side_effect=DatabaseError("DB temporarily unavailable"),
    ):
        with pytest.raises(DatabaseError):
            service_proposal_prepare({})
    buyer.refresh_from_db()
    assert buyer.status == "new"
    assert DRAFT_MARKER not in buyer.internal_note
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 0


@pytest.mark.django_db
def test_new_draft_marker_without_audit_proof_cannot_be_workitem(buyer):
    buyer.status = "reviewing"
    buyer.internal_note += "\n" + DRAFT_MARKER
    buyer.save(update_fields=["status", "internal_note"])
    result = handoff_prepared_inquiry(buyer.pk)
    assert result["state"] == "source_draft_audit_proof_missing"
    assert result["verified_effect"] is False
    assert WorkItem.objects.count() == 0
    assert not get_user_model().objects.filter(username=SERVICE_ACTOR_USERNAME).exists()


@pytest.mark.django_db
def test_tampered_customer_request_invalidates_provenance_digest(buyer):
    prepare_one(buyer.pk)
    buyer.message = "A separate, entirely changed private customer scope."
    buyer.save(update_fields=["message"])
    result = handoff_prepared_inquiry(buyer.pk)
    assert result["state"] == "source_draft_audit_proof_missing"
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_old_nonconsented_import_cannot_be_handed_off(buyer):
    buyer.internal_note = "Imported PHP record without consent"
    buyer.status = "reviewing"
    buyer.save(update_fields=["status", "internal_note"])
    assert handoff_prepared_inquiry(buyer.pk)["state"] == "consent_scope_or_draft_unverified"
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_closed_inquiry_does_not_create_pending_workitem(buyer):
    prepare_one(buyer.pk)
    buyer.status = "closed"
    buyer.save(update_fields=["status"])
    assert handoff_prepared_inquiry(buyer.pk)["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_scope_code_mismatch_blocks_routing_to_desk(buyer):
    prepare_one(buyer.pk)
    buyer.kind = "commercial"
    buyer.save(update_fields=["kind"])
    assert handoff_prepared_inquiry(buyer.pk)["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("inquiry_id", [None, True, False, 0, -5, "123", 2.0])
def test_invalid_inquiry_id_blocks_desk_creation(buyer, inquiry_id):
    with pytest.raises(ValueError, match="invalid_inquiry_id"):
        handoff_prepared_inquiry(inquiry_id)
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_nonexistent_inquiry_has_no_effect(db):
    assert handoff_prepared_inquiry(999999)["state"] == "inquiry_not_found"
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_staff_without_crm_change_permission_cannot_create_handoff(buyer):
    prepare_one(buyer.pk)
    bad_actor = get_user_model().objects.create_user(
        username="limited-operator-c10", is_staff=True, password=None,
    )
    result = handoff_prepared_inquiry(buyer.pk, created_by=bad_actor)
    assert result["state"] == "creator_not_authorized"
    assert result["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_real_owner_can_handoff_existing_prepared_proposal(buyer, owner):
    prepare_one(buyer.pk)
    result = handoff_prepared_inquiry(buyer.pk, created_by=owner)
    assert result["state"] == "desk_workitem_created"
    item = WorkItem.objects.get()
    assert item.created_by_id == owner.pk
    assert item.status == "open"
    assert not get_user_model().objects.filter(username=SERVICE_ACTOR_USERNAME).exists()


@pytest.mark.django_db
def test_admin_and_worker_handoff_use_same_identity_and_task_without_duplication(buyer, owner):
    service_proposal_prepare({})
    existing = WorkItem.objects.get()
    second = handoff_prepared_inquiry(buyer.pk, created_by=owner)
    assert second["state"] == "existing_desk_workitem"
    assert second["workitem_id"] == existing.pk
    assert WorkItem.objects.count() == 1
    assert WorkItem.objects.get().created_by_id == existing.created_by_id


@pytest.mark.django_db
def test_existing_finished_workitem_never_reopens(buyer):
    service_proposal_prepare({})
    WorkItem.objects.update(status="done")
    result = handoff_prepared_inquiry(buyer.pk)
    assert result["state"] == "existing_desk_workitem"
    assert WorkItem.objects.get().status == "done"
    assert WorkItem.objects.count() == 1


@pytest.mark.django_db
def test_ordinary_preparation_does_not_imply_fulfillment_or_cash(buyer):
    result = service_proposal_prepare({})
    assert result["evidence"]["cash_reconciled"] is False
    assert result["evidence"]["customer_contacted"] is False
    assert result["next_action"] == "owner_review_real_desk_workitem"
    assert Order.objects.count() == 0
