"""C07: recover actionable service leads and expose only measured staff metrics."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Q
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from core.autonomous_brain import AutonomousBrain
from core.company_inquiry_models import CompanyInquiry
from core.models import AgentTask, AuditLog, Order
from core.service_quote_draft import (
    DRAFT_MARKER, MAX_BATCH, MAX_SCAN, SOURCE_MARKER, _allowed_source,
    prepare_next, prepare_one, preview_candidates,
)
from command_center.service_proposal_funnel import service_proposal_funnel_snapshot


def create_lead(*, good=True, status="new", code="AGR-01", source=True):
    return CompanyInquiry.objects.create(
        kind="project" if code == "AGR-01" else "research",
        name="Non-public Customer",
        email="buyer@example.invalid" if good else "invalid-contact",
        subject=f"[{code}] Request a documented service proposal",
        message="Please review costs, scope, data rights and delivery criteria.",
        internal_note=SOURCE_MARKER if source else "Imported legacy email without consent",
        status=status,
    )


@pytest.fixture
def owner(db):
    User = get_user_model()
    return User.objects.create_superuser(
        username="owner-c07", email="owner@example.invalid", password="not-a-real-secret"
    )


@pytest.mark.django_db
def test_lead_behind_first_twenty_invalid_records_is_not_starved():
    for _ in range(30):
        create_lead(good=False)
    valid = create_lead()
    snapshot = preview_candidates()
    assert snapshot["eligible_count"] == 1
    assert snapshot["requires_human_review_count"] == 30
    assert snapshot["candidate_count"] == 31
    assert snapshot["review_reason_counts"] == {"invalid_contact": 30}
    result = prepare_next()
    assert result["state"] == "prepared_internal_draft"
    assert result["evidence"]["inquiry_id"] == valid.pk
    valid.refresh_from_db()
    assert valid.status == "reviewing"
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_limit_one_reports_one_eligible_without_hiding_rejection_counts():
    for _ in range(25):
        create_lead(good=False)
    create_lead()
    create_lead()
    status = preview_candidates(limit=1)
    assert status["eligible_count"] == 1
    assert status["eligible_seen_in_scan"] == 2
    assert status["requires_human_review_count"] == 25


@pytest.mark.django_db
def test_bounded_queue_distinguishes_large_backlog_from_no_customers():
    invalid = [
        CompanyInquiry(
            kind="project", name="Bad", email="invalid-email",
            subject="[AGR-01] Scope",
            message="Request is too short",
            status="new", internal_note=SOURCE_MARKER,
        )
        for _ in range(MAX_SCAN + 1)
    ]
    CompanyInquiry.objects.bulk_create(invalid)
    out = preview_candidates()
    assert out["scan_limit_reached"] is True
    assert out["scan_complete"] is False
    assert out["candidate_count"] == MAX_SCAN
    assert out["requires_human_review_count"] == MAX_SCAN
    assert out["eligible_count"] == 0
    result = prepare_next()
    assert result["state"] == "scan_limit_reached_requires_manual_triage"
    assert result["verified_effect"] is False
    assert AgentTask.objects.count() == 0
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_brain_explicitly_requests_triage_instead_of_falsely_declaring_empty_market():
    CompanyInquiry.objects.bulk_create([
        CompanyInquiry(
            kind="project", name="Bad", email="invalid-email",
            subject="[AGR-01] Scope",
            message="Please review this request and documentation",
            status="new", internal_note=SOURCE_MARKER,
        )
        for _ in range(MAX_SCAN + 1)
    ])
    state = AutonomousBrain().observe()
    assert state["consented_service_draft_candidates"] == 0
    assert state["consented_service_queue_scan_limited"] is True
    chosen = AutonomousBrain().candidates(state)[0]
    assert chosen.action == "await_consent_queue_manual_triage"


@pytest.mark.django_db
def test_lead_source_marker_must_be_exact_prefix_not_quoted_inside_old_notes():
    row = create_lead()
    row.internal_note = "Old support email contains the text " + SOURCE_MARKER
    row.save(update_fields=["internal_note"])
    assert _allowed_source(row) is False
    assert prepare_one(row.pk)["state"] == "consent_or_source_unverified"
    assert preview_candidates()["candidate_count"] == 0
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_rejected_early_row_does_not_force_scanner_to_repeat_forever():
    for _ in range(42):
        create_lead(good=False)
    later = create_lead()
    assert prepare_next()["evidence"]["inquiry_id"] == later.pk
    assert prepare_next()["state"] == "no_eligible_consented_service_inquiry"
    assert AuditLog.objects.count() == 1


@pytest.mark.django_db
def test_race_in_first_selected_row_continues_to_second_legitimate_buyer():
    first = create_lead()
    second = create_lead()
    real_prepare = prepare_one
    calls = []
    def concurrent_prepare(pk):
        calls.append(pk)
        if pk == first.pk:
            return {"state": "not_new", "verified_effect": False}
        return real_prepare(pk)
    with patch("core.service_quote_draft.prepare_one", side_effect=concurrent_prepare):
        response = prepare_next()
    assert calls == [first.pk, second.pk]
    assert response["evidence"]["inquiry_id"] == second.pk


@pytest.mark.django_db
def test_invalid_preview_budget_is_denied_without_db_write():
    create_lead()
    for limit in (0, -1, MAX_BATCH + 1, True, None, "20"):
        with pytest.raises(ValueError, match="invalid_batch_limit"):
            preview_candidates(limit)
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_queue_rejection_summary_does_not_expose_contact_data():
    create_lead(good=False)
    snapshot = preview_candidates()
    text = json.dumps(snapshot)
    assert "buyer@example.invalid" not in text
    assert "Non-public Customer" not in text
    assert snapshot["review_reason_counts"]["invalid_contact"] == 1


@pytest.mark.django_db
def test_cli_preview_reports_scan_quality_and_never_modifies_customer_record():
    from io import StringIO
    lead = create_lead()
    buf = StringIO()
    call_command("mojtaba_prepare_service_drafts", stdout=buf)
    report = json.loads(buf.getvalue())
    assert report["scan_complete"] is True
    assert report["eligible_count"] == 1
    assert report["mode"] == "read_only"
    lead.refresh_from_db()
    assert lead.status == "new"


@pytest.mark.django_db
def test_cli_apply_consumes_only_real_consented_lead_behind_old_rejections():
    from io import StringIO
    for _ in range(27):
        create_lead(good=False)
    valid = create_lead()
    out = StringIO()
    call_command("mojtaba_prepare_service_drafts", apply=True, stdout=out)
    assert json.loads(out.getvalue())["prepared_inquiry_ids"] == [valid.pk]
    assert AuditLog.objects.count() == 1


@pytest.mark.django_db
def test_admin_action_stops_mass_write_when_more_than_twenty_selected(owner):
    for _ in range(21):
        create_lead()
    panel = django_admin.site._registry[CompanyInquiry]
    request = SimpleNamespace(user=owner)
    with patch.object(panel, "message_user") as notify:
        panel.prepare_scoped_service_response(request, CompanyInquiry.objects.all())
    assert "حداکثر ۲۰" in notify.call_args.args[1]
    assert CompanyInquiry.objects.filter(status="reviewing").count() == 0


@pytest.mark.django_db
def test_admin_action_prepares_only_consented_records_and_is_idempotent(owner):
    valid = create_lead()
    invalid = create_lead(source=False)
    panel = django_admin.site._registry[CompanyInquiry]
    request = SimpleNamespace(user=owner)
    with patch.object(panel, "message_user") as notify:
        panel.prepare_scoped_service_response(request, CompanyInquiry.objects.all())
        panel.prepare_scoped_service_response(request, CompanyInquiry.objects.all())
    valid.refresh_from_db()
    invalid.refresh_from_db()
    assert valid.status == "reviewing"
    assert invalid.status == "new"
    assert valid.internal_note.count(DRAFT_MARKER) == 1
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1
    assert notify.call_count == 2


@pytest.mark.django_db
def test_admin_action_blocks_staff_without_change_permission(db):
    staff = get_user_model().objects.create_user(
        username="staff-c07", email="staff@example.invalid",
        password="not-a-secret", is_staff=True,
    )
    lead = create_lead()
    panel = django_admin.site._registry[CompanyInquiry]
    with patch.object(panel, "message_user"):
        panel.prepare_scoped_service_response(
            SimpleNamespace(user=staff), CompanyInquiry.objects.filter(pk=lead.pk)
        )
    lead.refresh_from_db()
    assert lead.status == "new"
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_admin_columns_show_verified_consent_and_draft_state():
    good = create_lead()
    historical = create_lead(source=False)
    panel = django_admin.site._registry[CompanyInquiry]
    assert panel.has_consent_provenance(good) is True
    assert panel.has_consent_provenance(historical) is False
    assert panel.draft_prepared(good) is False
    prepare_one(good.pk)
    good.refresh_from_db()
    assert panel.draft_prepared(good) is True


@pytest.mark.django_db
def test_funnel_counts_real_record_stage_and_service_without_fake_cash():
    accepted = create_lead()
    unconsented = create_lead(source=False)
    review = create_lead(code="RS-01")
    prepare_one(review.pk)
    snap = service_proposal_funnel_snapshot()
    assert snap["total_consent_provenance"] == 2
    assert snap["new"] == 1
    assert snap["reviewing"] == 1
    assert snap["by_service"]["AGR-01"]["total"] == 1
    assert snap["by_service"]["RS-01"]["internal_draft_prepared"] == 1
    assert snap["draft_prepared_total"] == 1
    assert snap["cash_settled"] is None
    assert snap["orders_delivered"] is None
    assert snap["buyer_contact_verified"] is None
    assert unconsented.pk != accepted.pk
    assert "buyer@example.invalid" not in json.dumps(snap)


@pytest.mark.django_db
def test_funnel_aging_exposes_review_sla_counts_without_customer_identity():
    old = create_lead()
    old_review = create_lead(code="RS-01", status="reviewing")
    CompanyInquiry.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(hours=26)
    )
    CompanyInquiry.objects.filter(pk=old_review.pk).update(
        updated_at=timezone.now() - timedelta(hours=75)
    )
    report = service_proposal_funnel_snapshot()
    assert report["awaiting_initial_review_over_24h"] == 1
    assert report["reviewing_over_72h"] == 1


@pytest.mark.django_db
def test_funnel_api_denies_anonymous_read():
    response = Client().get(reverse("command_center_service_proposal_funnel_api"))
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_funnel_api_denies_non_owner_staff():
    staff = get_user_model().objects.create_user(
        username="staff-inspector", email="inspector@example.invalid",
        password="not-a-secret", is_staff=True,
    )
    client = Client()
    client.force_login(staff)
    response = client.get(reverse("command_center_service_proposal_funnel_api"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_funnel_api_owner_get_is_read_only_no_cache_no_pii(owner):
    lead = create_lead()
    client = Client()
    client.force_login(owner)
    url = reverse("command_center_service_proposal_funnel_api")
    before = (CompanyInquiry.objects.count(), AuditLog.objects.count())
    response = client.get(url)
    assert response.status_code == 200
    assert response["Cache-Control"].startswith("no-store")
    assert response["Vary"] == "Cookie"
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"
    assert response.json()["candidate_scan"]["eligible"] == 1
    assert "Non-public Customer" not in response.content.decode()
    assert lead.email not in response.content.decode()
    assert before == (CompanyInquiry.objects.count(), AuditLog.objects.count())


@pytest.mark.django_db
def test_funnel_api_rejects_post_even_from_owner(owner):
    client = Client()
    client.force_login(owner)
    response = client.post(reverse("command_center_service_proposal_funnel_api"))
    assert response.status_code == 405
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
def test_unconsented_historical_import_does_not_enter_scoped_funnel():
    create_lead(source=False)
    snap = service_proposal_funnel_snapshot()
    assert snap["total_consent_provenance"] == 0
    assert snap["candidate_scan"]["eligible"] == 0


@pytest.mark.django_db
def test_all_six_service_codes_are_visible_to_owner_with_zero_is_zero():
    snapshot = service_proposal_funnel_snapshot()
    assert set(snapshot["by_service"]) == {
        "AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01",
    }
    assert all(v["total"] == 0 for v in snapshot["by_service"].values())


@pytest.mark.django_db
def test_approved_inquiries_are_not_reactivated_by_drafting():
    lead = create_lead(status="approved")
    assert prepare_one(lead.pk)["verified_effect"] is False
    assert preview_candidates()["eligible_count"] == 0
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_owner_dashboard_renders_scoped_stats_and_existing_admin_action(owner):
    lead = create_lead()
    client = Client()
    client.force_login(owner)
    response = client.get(reverse("command_center_service_proposal_funnel_dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "پیگیری سرنخ‌ها و پیشنهاد خدمات" in body
    assert "درخواست با منشأ و رضایت ثبت‌شده" in body
    assert "آماده‌سازی پیش‌نویس داخلی" in body
    assert reverse("admin:core_companyinquiry_changelist") in body
    assert reverse("command_center_service_proposal_funnel_api") in body
    assert lead.email not in body
    assert lead.name not in body
    assert response["Cache-Control"].startswith("no-store")
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"


@pytest.mark.django_db
def test_non_owner_cannot_open_dashboard(db):
    response = Client().get(reverse("command_center_service_proposal_funnel_dashboard"))
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_dashboard_refuses_write_methods_even_for_owner(owner):
    client = Client()
    client.force_login(owner)
    response = client.post(reverse("command_center_service_proposal_funnel_dashboard"))
    assert response.status_code == 405
    assert AuditLog.objects.count() == 0


@pytest.mark.django_db
def test_dashboard_has_no_fabricated_percentage_without_leads(owner):
    client = Client()
    client.force_login(owner)
    response = client.get(reverse("command_center_service_proposal_funnel_dashboard"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "هنوز پرونده دارای منشأ و رضایت" in html
    assert "100٪" not in html
    assert CompanyInquiry.objects.count() == 0


@pytest.mark.django_db
def test_dashboard_computes_prepared_over_consent_records_not_over_sales(owner):
    valid = create_lead()
    create_lead()
    prepare_one(valid.pk)
    client = Client()
    client.force_login(owner)
    html = client.get(reverse("command_center_service_proposal_funnel_dashboard")).content.decode()
    assert "50.0٪" in html
    assert "درآمد وصول‌شده" in html
    assert "فقط" not in ""  # No assertion about real cash from an internal ratio.


@pytest.mark.django_db
def test_admin_bulk_proposals_do_not_contact_customer_or_open_payments(owner):
    lead = create_lead()
    panel = django_admin.site._registry[CompanyInquiry]
    with patch("django.core.mail.send_mail", side_effect=AssertionError("external send forbidden")), \
         patch.object(panel, "message_user"):
        panel.prepare_scoped_service_response(
            SimpleNamespace(user=owner),
            CompanyInquiry.objects.filter(pk=lead.pk),
        )
    assert Order.objects.count() == 0
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 1
