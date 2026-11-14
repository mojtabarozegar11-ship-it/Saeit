"""C11 CLI and owner-dashboard coverage for stranded real service requests."""
import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.urls import reverse

from command_center.models import WorkItem
from core.company_inquiry_models import CompanyInquiry
from core.models import AuditLog, Order
from core.service_quote_draft import SOURCE_MARKER, prepare_one


@pytest.fixture
def leads(db):
    records = []
    for i in range(3):
        row = CompanyInquiry.objects.create(
            kind="project",
            name="Confidential Service Customer",
            email=f"private-service-{i}@example.invalid",
            subject="[AGR-01] Private commercial research request",
            message="Please prepare a documented farm economics scope and cost study.",
            status="new",
            internal_note=SOURCE_MARKER,
        )
        assert prepare_one(row.pk)["verified_effect"] is True
        records.append(row)
    return records


@pytest.mark.django_db
def test_cli_default_is_readonly_and_reports_real_stranded_count(leads):
    out = StringIO()
    call_command("mojtaba_reconcile_service_handoffs", stdout=out)
    result = json.loads(out.getvalue())
    assert result["eligible_verified_handoffs"] == 3
    assert result["writes_performed"] == 0
    assert result["mode"] == "read_only"
    assert result["cash_received"] is None
    assert WorkItem.objects.count() == 0
    assert "private-service-0@" not in out.getvalue()


@pytest.mark.django_db
def test_cli_apply_with_limit_two_creates_exactly_two_tasks_without_emails(leads):
    out = StringIO()
    call_command("mojtaba_reconcile_service_handoffs",
                 apply=True, limit=2, stdout=out)
    data = json.loads(out.getvalue())
    assert data["created_workitem_count"] == 2
    assert len(data["created_workitem_ids"]) == 2
    assert data["customer_contacted"] is False
    assert WorkItem.objects.count() == 2
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_cli_second_apply_reuses_remaining_and_does_not_duplicate(leads):
    for _ in range(2):
        call_command("mojtaba_reconcile_service_handoffs",
                     apply=True, limit=20, stdout=StringIO())
    assert WorkItem.objects.count() == 3
    assert WorkItem.objects.values("source_type", "source_id").distinct().count() == 3
    assert AuditLog.objects.filter(action="service_response_draft_prepared").count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize("bad", [0, -1, 21, True, None])
def test_cli_rejects_bad_or_unbounded_limit(leads, bad):
    with pytest.raises(CommandError):
        call_command("mojtaba_reconcile_service_handoffs", apply=True,
                     limit=bad, stdout=StringIO())
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_cli_does_not_create_draft_for_nonconsented_legacy_record(db):
    CompanyInquiry.objects.create(
        kind="project", name="Old Import", email="import@example.invalid",
        subject="[AGR-01] Historic import without consent",
        message="Historic contact request that cannot be used for outreach.",
        internal_note="Imported without consent", status="new",
    )
    out = StringIO()
    call_command("mojtaba_reconcile_service_handoffs", apply=True, stdout=out)
    assert json.loads(out.getvalue())["created_workitem_count"] == 0
    assert WorkItem.objects.count() == 0


@pytest.mark.django_db
def test_owner_funnel_reports_actual_stranded_count_and_recovery(leads):
    from command_center.service_proposal_funnel import service_proposal_funnel_snapshot
    before = service_proposal_funnel_snapshot()
    assert before["stranded_desk_handoff"]["verified_count"] == 3
    assert before["stranded_desk_handoff"]["scan_complete"] is True
    call_command("mojtaba_reconcile_service_handoffs", apply=True,
                 limit=2, stdout=StringIO())
    after = service_proposal_funnel_snapshot()
    assert after["stranded_desk_handoff"]["verified_count"] == 1
    assert after["workitems_total"] == 2
    assert after["cash_settled"] is None


@pytest.mark.django_db
def test_owner_only_dashboard_shows_stranded_proposals_no_customer_pii(leads):
    User = get_user_model()
    owner = User.objects.create_superuser(
        username="owner-recovery-c11", password="unused-test-secret",
        email="owner-recovery@example.invalid",
    )
    client = Client()
    client.force_login(owner)
    r = client.get(reverse("command_center_service_proposal_funnel_dashboard"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "پیشنهادهای دارای سند اما بدون ارجاع اجرایی" in html
    assert "Confidential Service Customer" not in html
    assert "private-service-0" not in html
    assert "درآمد وصول‌شده" in html or "وصول وجه" in html
