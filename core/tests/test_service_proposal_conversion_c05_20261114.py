"""C05: Revenue-oriented first-party CRM drafting without customer contact.

This suite verifies an actual CRM state change, not an external sale.
"""
import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.autonomous_brain import AutonomousBrain
from core.company_inquiry_models import CompanyInquiry
from core.models import Agent, AgentTask, AuditLog, Order, Product
from core.service_quote_draft import (
    BOT_ID, DRAFT_MARKER, KIND_BY_CODE, MAX_BATCH, SOURCE_MARKER,
    _eligible, prepare_next, prepare_one, preview_candidates,
    render_internal_draft,
)
from core.service_sales_controls import SERVICE_CARDS

PUBLIC_MARKER = SOURCE_MARKER


@pytest.fixture
def lead(db):
    return CompanyInquiry.objects.create(
        kind="project",
        name="Private Farm Customer",
        organization="Confidential Buyer",
        email="private-buyer@example.invalid",
        phone="PRIVATE-PHONE-0199",
        subject="[AGR-01] Farm profitability review",
        message="We want a documented unit economics analysis and delivery review.",
        internal_note=PUBLIC_MARKER,
        status="new",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("code", list(KIND_BY_CODE))
def test_real_six_service_scopes_have_truthful_offer_draft(code):
    row = CompanyInquiry.objects.create(
        kind=KIND_BY_CODE[code],
        name="Client",
        email="client@example.invalid",
        subject=f"[{code}] Scope review",
        message="Please review a realistic scope, inputs, deliverables and dependencies.",
        internal_note=PUBLIC_MARKER,
    )
    result = prepare_one(row.pk)
    assert result["state"] == "prepared_internal_draft"
    assert result["verified_effect"] is True
    row.refresh_from_db()
    assert row.status == "reviewing"
    assert SERVICE_CARDS[code]["title_fa"] in row.internal_note
    for deliverable in SERVICE_CARDS[code]["deliverables"]:
        assert deliverable in row.internal_note
    assert SERVICE_CARDS[code]["limitation"] in row.internal_note
    assert DRAFT_MARKER in row.internal_note
    assert "قیمت و ارز فقط بعد از برآورد هزینه" in row.internal_note
    assert result["customer_contacted"] is False


@pytest.mark.django_db
def test_draft_does_not_replicate_customer_data_or_make_financial_entries(lead):
    before = (Order.objects.count(), Product.objects.count())
    quote = prepare_one(lead.pk)
    lead.refresh_from_db()
    prepared_section = lead.internal_note.split(DRAFT_MARKER, 1)[1]
    assert lead.email not in prepared_section
    assert lead.name not in prepared_section
    assert lead.phone not in prepared_section
    assert lead.message not in prepared_section
    assert (Order.objects.count(), Product.objects.count()) == before
    assert quote["external_payment_received"] is None
    assert quote["next_action"] == "owner_review_service_proposal"


@pytest.mark.django_db
def test_consent_is_required_and_absence_cannot_modify_lead(lead):
    lead.internal_note = "Imported CRM history without explicit processing consent."
    lead.save(update_fields=("internal_note",))
    before_note = lead.internal_note
    assert prepare_one(lead.pk)["state"] == "consent_or_source_unverified"
    lead.refresh_from_db()
    assert lead.internal_note == before_note
    assert lead.status == "new"
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["reviewing", "approved", "closed"])
def test_closed_or_reviewed_inquiries_cannot_be_reopened_by_bot(lead, status):
    lead.status = status
    lead.save(update_fields=("status",))
    assert prepare_one(lead.pk)["state"] == "not_new"
    lead.refresh_from_db()
    assert lead.status == status
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_draft_is_exactly_once_no_duplicate_audit_entries(lead):
    assert prepare_one(lead.pk)["verified_effect"] is True
    assert prepare_one(lead.pk)["verified_effect"] is False
    lead.refresh_from_db()
    assert lead.internal_note.count(DRAFT_MARKER) == 1
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("code,kind", [
    ("XYZ-01", "project"),
    ("AGR-01", "commercial"),
    ("RS-01", "project"),
    ("WEB-01", "research"),
    ("SEO-01", "project"),
])
def test_unknown_or_mismatched_service_is_not_quoted(lead, code, kind):
    lead.kind = kind
    lead.subject = f"[{code}] Authorized business service inquiry"
    lead.save(update_fields=("kind", "subject"))
    assert prepare_one(lead.pk)["state"] == "unknown_or_mismatched_service"
    lead.refresh_from_db()
    assert lead.status == "new"
    assert DRAFT_MARKER not in lead.internal_note


@pytest.mark.django_db
@pytest.mark.parametrize("subject", [
    "AGR-01 Service request",
    "[AGR-01]fake without space",
    "[AGR-01] Service\nheader injection",
    "[AGR-01] Service\rheader injection",
    "[AGR-01] ",
])
def test_malformed_subject_is_rejected_before_state_change(lead, subject):
    lead.subject = subject
    lead.save(update_fields=("subject",))
    assert prepare_one(lead.pk)["verified_effect"] is False
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("field,value,expected", [
    ("name", "x", "invalid_name"),
    ("name", "x" * 181, "invalid_name"),
    ("message", "too short", "invalid_message"),
    ("message", "x" * 3501, "invalid_message"),
    ("email", "no-at-sign", "invalid_contact"),
    ("email", "", "invalid_contact"),
])
def test_invalid_contact_material_never_reaches_sales_pipeline(lead, field, value, expected):
    setattr(lead, field, value)
    lead.save(update_fields=(field,))
    assert prepare_one(lead.pk)["state"] == expected
    lead.refresh_from_db()
    assert lead.status == "new"


@pytest.mark.django_db
def test_excessively_long_private_note_fails_without_truncating_history(lead):
    lead.internal_note = PUBLIC_MARKER + ("X" * 11900)
    lead.save(update_fields=("internal_note",))
    assert prepare_one(lead.pk)["state"] == "internal_note_capacity_exhausted"
    lead.refresh_from_db()
    assert lead.internal_note.endswith("X" * 11900)


@pytest.mark.django_db
def test_nonexistent_or_invalid_ids_do_not_write(db):
    assert prepare_one(999999)["state"] == "not_found"
    for invalid in (0, -1, True, "5", None):
        with pytest.raises(ValueError, match="invalid_inquiry_id"):
            prepare_one(invalid)
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_audit_provenance_contains_no_customer_personal_information(lead):
    result = prepare_one(lead.pk)
    rows = list(AuditLog.objects.filter(action="service_response_draft_prepared"))
    assert len(rows) == 1
    row = rows[0]
    text = json.dumps(row.after_state)
    assert row.actor_id == BOT_ID
    assert row.target_type == "CompanyInquiry"
    assert row.target_id == str(lead.pk)
    assert row.after_state["human_review_required"] is True
    assert row.after_state["buyer_contacted"] is False
    assert row.after_state["cash_settled"] is False
    assert lead.email not in text
    assert lead.phone not in text
    assert lead.message not in text
    assert result["evidence"]["request_sha256_prefix"] in row.trace_id


@pytest.mark.django_db
def test_preview_is_read_only_and_has_no_pii(lead):
    before = lead.internal_note
    out = preview_candidates(limit=20)
    lead.refresh_from_db()
    assert out["candidate_count"] == 1
    assert out["eligible_count"] == 1
    assert out["mode"] == "read_only"
    assert out["customer_details_exposed"] is False
    assert out["cash_receipts_verified"] is None
    assert lead.internal_note == before
    assert AuditLog.objects.count() == 0
    assert lead.email not in json.dumps(out)


@pytest.mark.django_db
@pytest.mark.parametrize("limit", [0, -1, 21, True, None])
def test_unbounded_or_ambiguous_preview_is_rejected(lead, limit):
    with pytest.raises(ValueError, match="invalid_batch_limit"):
        preview_candidates(limit)


@pytest.mark.django_db
def test_old_unconsented_record_is_not_selected_as_eligible(lead):
    CompanyInquiry.objects.create(
        kind="project", name="Old Contact", email="old@example.invalid",
        subject="[AGR-01] No consent", message="Please give detailed scope review.",
        internal_note="legacy PHP source unverified", status="new",
    )
    assert preview_candidates()["eligible_count"] == 1
    result = prepare_next()
    assert result["state"] == "prepared_internal_draft"
    assert AuditLog.objects.count() == 1


@pytest.mark.django_db
def test_prepare_next_never_generates_a_sale_when_no_real_lead(db):
    result = prepare_next()
    assert result["verified_effect"] is False
    assert result["state"] == "no_eligible_consented_service_inquiry"
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
def test_command_default_preview_cannot_write_to_crm(lead):
    out = StringIO()
    call_command("mojtaba_prepare_service_drafts", stdout=out)
    lead.refresh_from_db()
    data = json.loads(out.getvalue())
    assert data["mode"] == "read_only"
    assert data["eligible_count"] == 1
    assert lead.status == "new"
    assert AuditLog.objects.count() == 0
    assert lead.email not in out.getvalue()


@pytest.mark.django_db
def test_command_explicit_apply_produces_one_real_internal_draft(lead):
    out = StringIO()
    with patch("django.core.mail.send_mail", side_effect=AssertionError("No outgoing mail")):
        call_command("mojtaba_prepare_service_drafts", apply=True, stdout=out)
    result = json.loads(out.getvalue())
    assert result["mode"] == "internal_crm_draft_only"
    assert result["prepared_count"] == 1
    assert result["prepared_inquiry_ids"] == [lead.pk]
    assert result["email_sent"] is False
    assert result["payment_enabled"] is False
    assert result["sale_or_delivery_verified"] is False
    lead.refresh_from_db()
    assert lead.status == "reviewing"


@pytest.mark.django_db
def test_explicit_id_mode_does_not_apply_an_unrelated_lead(lead):
    other = CompanyInquiry.objects.create(
        kind="project", name="Other", email="other@example.invalid",
        subject="[AGR-01] New request",
        message="We need a complete farm profitability analysis and review.",
        internal_note=PUBLIC_MARKER,
    )
    out = StringIO()
    call_command(
        "mojtaba_prepare_service_drafts",
        apply=True, inquiry_id=other.pk, stdout=out,
    )
    lead.refresh_from_db()
    other.refresh_from_db()
    assert lead.status == "new"
    assert other.status == "reviewing"
    assert AuditLog.objects.count() == 1


@pytest.mark.django_db
def test_command_is_idempotent_and_reports_no_second_creation(lead):
    first = StringIO()
    call_command("mojtaba_prepare_service_drafts", apply=True, stdout=first)
    second = StringIO()
    call_command("mojtaba_prepare_service_drafts", apply=True, stdout=second)
    assert json.loads(second.getvalue())["prepared_count"] == 0
    assert AuditLog.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("limit, inquiry_id", [
    (0, None), (21, None), (-1, None), (2, 1), (1, -1), (1, 0),
])
def test_command_refuses_invalid_limit_and_id(lead, limit, inquiry_id):
    with pytest.raises(CommandError):
        call_command(
            "mojtaba_prepare_service_drafts",
            apply=True, limit=limit, inquiry_id=inquiry_id,
        )
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_single_economic_bot_is_the_only_gateway_dispatcher_for_consent_lead(lead):
    # No independent bot or cron is registered for the service; the existing
    # master gets one low-risk capability and builds a CRM draft through it.
    call_command("seed_online_income_agents", stdout=StringIO())
    master = Agent.objects.get(code="economic-master-agent")
    cap = master.capabilities.get(code="income_service_proposal_prepare")
    assert cap.risk_level == "low"
    state = AutonomousBrain().observe()
    assert state["consented_service_draft_candidates"] == 1
    assert AutonomousBrain().candidates(state)[0].action == "income_service_proposal_prepare"
    call_command("online_income_cycle", stdout=StringIO())
    queued = AgentTask.objects.filter(
        agent=master, capability_code="income_service_proposal_prepare",
    ).get()
    assert queued.status == "queued"
    call_command("run_economic_worker", stdout=StringIO())
    queued.refresh_from_db()
    lead.refresh_from_db()
    assert queued.status == "completed"
    assert queued.output_data["verified_effect"] is True
    assert queued.output_data["evidence"]["inquiry_id"] == lead.pk
    assert lead.status == "reviewing"
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1
    assert Product.objects.filter(active=True).count() == 0
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_commercial_brain_does_not_claim_lead_when_without_consent(lead):
    lead.internal_note = "No consent from historical sources."
    lead.save(update_fields=("internal_note",))
    assert AutonomousBrain().observe()["consented_service_draft_candidates"] == 0


def test_service_code_mapping_matches_authoritative_catalogue():
    assert set(KIND_BY_CODE) == set(SERVICE_CARDS)
    assert MAX_BATCH == 20
    assert BOT_ID == "mojtaba.bot.ai"
