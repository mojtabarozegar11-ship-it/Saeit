"""Owner-only queue regressions against isolated Django test database."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from command_center.lead_workqueue import (
    PAGE_SIZE, lead_workqueue_snapshot,
)
from core.company_inquiry_models import CompanyInquiry


class LeadWorkqueueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        model = get_user_model()
        cls.owner = model.objects.create_superuser(
            username="lead_queue_owner_c03", password="local-only-pass",
            email="queue-owner@example.invalid"
        )
        cls.staff = model.objects.create_user(
            username="lead_queue_staff_c03", password="local-only-pass",
            is_staff=True,
        )
        cls.viewer = model.objects.create_user(
            username="lead_queue_reader_c03", password="local-only-pass",
        )

    def setUp(self):
        self.url = reverse("command_center_lead_workqueue_api")

    def _lead(self, *, code="AGR-01", kind="project", status="new", age_days=0):
        lead = CompanyInquiry.objects.create(
            kind=kind, status=status,
            name="Sensitive client name",
            email="unique-client@example.invalid",
            phone="+44 123 PRIVATE",
            organization="Sensitive company name",
            subject=f"[{code}] Sensitive buyer's scope",
            message="Sensitive confidential message and special pricing",
        )
        if age_days:
            CompanyInquiry.objects.filter(pk=lead.pk).update(
                created_at=timezone.now() - timedelta(days=age_days)
            )
        lead.refresh_from_db()
        return lead

    def _get(self, query=""):
        self.client.force_login(self.owner)
        return self.client.get(self.url + query)

    def test_owner_can_read_private_workqueue(self):
        r = self._get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["agent"], "mojtaba.bot.ai")
        self.assertTrue(r.json()["owner_only"])

    def test_no_anonymous_access(self):
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_staff_cannot_view_owner_queue(self):
        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_non_staff_cannot_view_owner_queue(self):
        self.client.force_login(self.viewer)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_post_is_rejected(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_empty_queue_is_valid(self):
        d = self._get().json()
        self.assertEqual(d["matching_open_requests"], 0)
        self.assertEqual(d["items"], [])
        self.assertFalse(d["has_more"])

    def test_status_closed_is_not_actionable(self):
        self._lead(status="closed")
        self.assertEqual(self._get().json()["matching_open_requests"], 0)

    def test_unknown_open_status_is_kept_for_review(self):
        self._lead(status="needs-manual-review")
        self.assertEqual(self._get().json()["matching_open_requests"], 1)

    def test_future_lead_is_excluded(self):
        lead = self._lead()
        CompanyInquiry.objects.filter(pk=lead.pk).update(
            created_at=timezone.now() + timedelta(days=2)
        )
        self.assertEqual(self._get().json()["matching_open_requests"], 0)

    def test_request_is_exposed_by_id_not_personal_data(self):
        lead = self._lead()
        item = self._get().json()["items"][0]
        self.assertEqual(item["inquiry_id"], lead.pk)
        self.assertNotIn("email", item)
        self.assertNotIn("name", item)
        self.assertNotIn("subject", item)

    def test_payload_has_no_raw_pii(self):
        self._lead()
        body = self._get().content.decode()
        for secret in (
            "Sensitive client name", "Sensitive company name", "+44 123 PRIVATE",
            "unique-client@example.invalid", "Sensitive confidential message",
        ):
            self.assertNotIn(secret, body)

    def test_service_code_extracted_from_known_prefix(self):
        self._lead(code="RS-02", kind="research")
        self.assertEqual(self._get().json()["items"][0]["service_code"], "RS-02")

    def test_unknown_service_code_does_not_leak_subject(self):
        self._lead(code="UNKNOWN-7")
        self.assertIsNone(self._get().json()["items"][0]["service_code"])

    def test_admin_link_is_internal_relative_path(self):
        lead = self._lead()
        path = self._get().json()["items"][0]["admin_detail_path"]
        self.assertEqual(path, reverse("admin:core_companyinquiry_change", args=[lead.pk]))
        self.assertTrue(path.startswith("/admin/"))

    def test_new_recent_lead_is_first_review(self):
        self._lead(status="new")
        self.assertEqual(self._get().json()["items"][0]["priority"], "first_review")

    def test_recent_reviewing_lead_needs_follow_up(self):
        self._lead(status="reviewing")
        self.assertEqual(self._get().json()["items"][0]["priority"], "follow_up")

    def test_over_seven_days_is_high_priority(self):
        self._lead(age_days=9)
        self.assertEqual(self._get().json()["items"][0]["priority"], "overdue_7d")

    def test_over_thirty_days_is_urgent(self):
        self._lead(age_days=31)
        self.assertEqual(self._get().json()["items"][0]["priority"], "overdue_30d")

    def test_oldest_first_order_is_stable(self):
        recent = self._lead(age_days=1)
        older = self._lead(age_days=18)
        ids = [x["inquiry_id"] for x in self._get().json()["items"]]
        self.assertEqual(ids, [older.pk, recent.pk])

    def test_filter_by_research_kind(self):
        self._lead(code="RS-01", kind="research")
        self._lead(code="WEB-01", kind="commercial")
        d = self._get("?kind=research").json()
        self.assertEqual(d["matching_open_requests"], 1)
        self.assertEqual(d["items"][0]["kind"], "research")

    def test_filter_by_unreviewed_status(self):
        self._lead(status="new")
        self._lead(status="reviewing")
        d = self._get("?status=new").json()
        self.assertEqual(d["matching_open_requests"], 1)
        self.assertEqual(d["items"][0]["status"], "new")

    def test_filter_combined_kind_and_status(self):
        self._lead(code="RS-01", kind="research", status="new")
        self._lead(code="RS-02", kind="research", status="reviewing")
        self._lead(code="WEB-01", kind="commercial", status="new")
        d = self._get("?status=new&kind=research").json()
        self.assertEqual(d["matching_open_requests"], 1)

    def test_invalid_status_returns_400_without_snapshot(self):
        x = self._get("?status=paid")
        self.assertEqual(x.status_code, 400)
        self.assertEqual(set(x.json()), {"error"})

    def test_invalid_kind_returns_400(self):
        self.assertEqual(self._get("?kind=wrong").status_code, 400)

    def test_zero_page_is_rejected(self):
        self.assertEqual(self._get("?page=0").status_code, 400)

    def test_negative_page_is_rejected(self):
        self.assertEqual(self._get("?page=-1").status_code, 400)

    def test_noncanonical_page_string_is_rejected(self):
        self.assertEqual(self._get("?page=01").status_code, 400)

    def test_excessive_page_is_rejected(self):
        self.assertEqual(self._get("?page=101").status_code, 400)

    def test_25_row_limit_and_has_more(self):
        for i in range(PAGE_SIZE + 2):
            self._lead(code="AGR-01", status="new")
        d = self._get().json()
        self.assertEqual(len(d["items"]), PAGE_SIZE)
        self.assertTrue(d["has_more"])
        self.assertEqual(d["matching_open_requests"], PAGE_SIZE + 2)

    def test_next_page_does_not_repeat_first_page(self):
        for i in range(PAGE_SIZE + 2):
            self._lead(status="new")
        first = self._get("?page=1").json()
        second = self._get("?page=2").json()
        self.assertEqual(len(second["items"]), 2)
        self.assertFalse(second["has_more"])
        self.assertTrue(
            set(x["inquiry_id"] for x in first["items"]).isdisjoint(
                x["inquiry_id"] for x in second["items"]
            )
        )

    def test_cache_is_private_and_noindex(self):
        r = self._get()
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("noindex", r["X-Robots-Tag"])
        self.assertEqual(r["Vary"], "Cookie")

    def test_no_fabricated_settlement_or_delivery(self):
        self._lead(status="approved")
        r = self._get().json()
        self.assertIsNone(r["settled_cash"])
        self.assertIsNone(r["delivery_evidence"])
        self.assertIn("not_signed_contract", r["stage_approved_means"])

    def test_same_bot_agent_can_read_queue(self):
        from core.economic_master_agent import EconomicMasterAgent
        self._lead(code="WEB-01", kind="commercial")
        data = EconomicMasterAgent().inspect_lead_workqueue_readonly(kind="commercial")
        self.assertEqual(data["agent"], "mojtaba.bot.ai")
        self.assertEqual(data["matching_open_requests"], 1)

    def test_pure_queue_api_rejects_bool_page(self):
        with self.assertRaises(ValueError):
            lead_workqueue_snapshot(page=True)

    def test_pure_queue_api_rejects_unexpected_kind(self):
        with self.assertRaises(ValueError):
            lead_workqueue_snapshot(kind="payment")

    def test_owner_queue_does_not_change_lead_status(self):
        lead = self._lead(status="new")
        self._get()
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")
