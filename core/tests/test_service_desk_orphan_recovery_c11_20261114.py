"""C11: autonomous recovery of real prepared buyer scopes stranded without desk tasks."""
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import transaction

from command_center.models import WorkItem
from core.autonomous_brain import AutonomousBrain
from core.company_inquiry_models import CompanyInquiry
from core.economic_tool_pack import service_proposal_prepare
from core.models import AgentTask, AuditLog, Order
from core.service_lead_handoff import (
    MAX_ORPHAN_SCAN, SERVICE_ACTOR_USERNAME,
    orphaned_handoff_snapshot, recover_one_orphaned_handoff,
)
from core.service_quote_draft import SOURCE_MARKER, DRAFT_MARKER, prepare_one


@pytest.fixture
def prepared(db):
    obj = CompanyInquiry.objects.create(
        kind="project", name="Client From Yesterday",
        email="buyer-private@example.invalid",
        subject="[AGR-01] Profitable farm service scope",
        message="Please prepare a professional agricultural economics cost analysis.",
        internal_note=SOURCE_MARKER, status="new",
    )
    receipt = prepare_one(obj.pk)
    assert receipt["verified_effect"] is True
    return obj


@pytest.mark.django_db
def test_snapshot_finds_one_independently_audited_orphaned_buyer(prepared):
    snapshot = orphaned_handoff_snapshot()
    assert snapshot["verified_candidate_count"] == 1
    assert snapshot["verified_inquiry_ids_internal"] == [prepared.pk]
    assert snapshot["inspected"] == 1
    assert snapshot["scan_complete"] is True
    assert snapshot["cash_received"] is None
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_orphan_is_recovered_as_real_workitem_not_fake_buyer_contact(prepared):
    result = recover_one_orphaned_handoff()
    assert result["state"] == "evidenced_draft_handoff_recovered"
    assert result["verified_effect"] is True
    assert result["evidence"]["inquiry_id"] == prepared.pk
    assert result["evidence"]["cash_reconciled"] is False
    assert WorkItem.objects.get(pk=result["evidence"]["workitem_id"]).status == "open"
    assert prepared.status == "reviewing"
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_auto_master_gateway_recovers_prepared_proposals(prepared):
    result = service_proposal_prepare({})
    assert result["state"] == "evidenced_draft_handoff_recovered"
    assert result["verified_effect"] is True
    assert WorkItem.objects.count() == 1
    assert prepared.pk == WorkItem.objects.get().source_id or str(prepared.pk) == WorkItem.objects.get().source_id


@pytest.mark.django_db
def test_brain_prioritizes_verified_orphan_over_self_improvement(prepared):
    observation = AutonomousBrain().observe()
    assert observation["consented_service_draft_candidates"] == 0
    assert observation["verified_orphaned_service_handoffs"] == 1
    chosen = AutonomousBrain().candidates(observation)[0]
    assert chosen.action == "income_service_proposal_prepare"
    assert "Recover" in chosen.reason


@pytest.mark.django_db
def test_queue_and_worker_recover_orphaned_desk_task(prepared):
    call_command("seed_online_income_agents", stdout=StringIO())
    call_command("online_income_cycle", stdout=StringIO())
    task = AgentTask.objects.get(capability_code="income_service_proposal_prepare")
    assert task.status == "queued"
    call_command("run_economic_worker", stdout=StringIO())
    task.refresh_from_db()
    assert task.status == "completed"
    assert task.output_data["verified_effect"] is True
    assert task.output_data["evidence"]["desk_handoff_verified"] is True
    assert WorkItem.objects.count() == 1


@pytest.mark.django_db
def test_worker_recovery_does_not_duplicate_draft_or_audit(prepared):
    prepare_count = AuditLog.objects.filter(action="service_response_draft_prepared").count()
    result = service_proposal_prepare({})
    prepared.refresh_from_db()
    assert prepared.internal_note.count(DRAFT_MARKER) == 1
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == prepare_count
    assert WorkItem.objects.count() == 1
    assert result["verified_effect"] is True


@pytest.mark.django_db
def test_recovery_is_idempotent_and_keeps_existing_done_task(prepared):
    first = recover_one_orphaned_handoff()
    WorkItem.objects.update(status="done")
    second = recover_one_orphaned_handoff()
    assert first["verified_effect"] is True
    assert second["verified_effect"] is False
    assert WorkItem.objects.get().status == "done"
    assert WorkItem.objects.count() == 1


@pytest.mark.django_db
def test_forged_note_without_audit_is_not_a_valid_recovery_candidate(prepared):
    AuditLog.objects.filter(action="service_response_draft_prepared").delete()
    snapshot = orphaned_handoff_snapshot()
    assert snapshot["verified_candidate_count"] == 0
    assert recover_one_orphaned_handoff()["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_modified_buyer_scope_invalidates_orphan_proof(prepared):
    prepared.subject = "[AGR-01] Edited customer request requiring new approval"
    prepared.save(update_fields=["subject"])
    assert orphaned_handoff_snapshot()["verified_candidate_count"] == 0
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_existing_prepared_but_closed_customer_is_not_reopened(prepared):
    prepared.status = "closed"
    prepared.save(update_fields=["status"])
    assert orphaned_handoff_snapshot()["verified_candidate_count"] == 0
    assert recover_one_orphaned_handoff()["verified_effect"] is False


@pytest.mark.django_db
def test_nonconsented_import_with_audit_marker_in_middle_is_not_imported(prepared):
    prepared.internal_note = "Old unrelated CRM text " + SOURCE_MARKER + DRAFT_MARKER
    prepared.save(update_fields=["internal_note"])
    assert orphaned_handoff_snapshot()["verified_candidate_count"] == 0
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_snapshot_never_claims_payment_or_prints_customer_body(prepared):
    snapshot = orphaned_handoff_snapshot()
    text = repr(snapshot)
    assert prepared.name not in text
    assert prepared.email not in text
    assert prepared.message not in text
    assert snapshot["cash_received"] is None
    assert snapshot["customer_contacted"] is False


@pytest.mark.django_db
def test_more_than_five_hundred_candidates_have_explicit_incomplete_state(db):
    CompanyInquiry.objects.bulk_create([
        CompanyInquiry(
            kind="project", name="Historic CRM Record",
            email="unverified@example.invalid",
            subject="[AGR-01] Imported scope", message="Prior imported text without trace",
            status="reviewing",
            internal_note=SOURCE_MARKER + "\n" + DRAFT_MARKER,
        )
        for _ in range(MAX_ORPHAN_SCAN + 1)
    ])
    result = orphaned_handoff_snapshot()
    assert result["inspected"] == MAX_ORPHAN_SCAN
    assert result["uninspected"] == 1
    assert result["scan_complete"] is False
    assert result["verified_candidate_count"] == 0
    response = recover_one_orphaned_handoff()
    assert response["state"] == "orphan_queue_incomplete_requires_review"
    assert response["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_recent_verified_buyer_not_starved_behind_501_invalid_history(prepared):
    CompanyInquiry.objects.bulk_create([
        CompanyInquiry(
            kind="project", name="Historic CRM Record",
            email="unverified@example.invalid",
            subject="[AGR-01] Imported scope", message="Imported, lacks audit",
            status="reviewing", internal_note=SOURCE_MARKER + "\n" + DRAFT_MARKER,
        )
        for _ in range(MAX_ORPHAN_SCAN + 1)
    ])
    snapshot = orphaned_handoff_snapshot()
    assert snapshot["verified_candidate_count"] == 1
    outcome = recover_one_orphaned_handoff()
    assert outcome["verified_effect"] is True
    assert WorkItem.objects.count() == 1


@pytest.mark.django_db
def test_recovery_handles_concurrent_completion_without_false_success(prepared):
    # Snapshot can include a record that a staff member completes before its
    # row is re-locked. Recheck inside handoff_prepared_inquiry is the gate.
    with patch(
        "core.service_lead_handoff.handoff_prepared_inquiry",
        return_value={"state": "existing_desk_workitem", "verified_effect": False},
    ):
        outcome = recover_one_orphaned_handoff()
    assert outcome["verified_effect"] is False
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_no_orphan_does_not_create_an_inactive_user_account(db):
    result = recover_one_orphaned_handoff()
    assert result["verified_effect"] is False
    from django.contrib.auth import get_user_model
    assert get_user_model().objects.filter(username=SERVICE_ACTOR_USERNAME).count() == 0
