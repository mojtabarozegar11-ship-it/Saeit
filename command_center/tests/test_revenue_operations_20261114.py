"""Database regressions for the owner-only mojtaba.bot.ai revenue-operations API.

No production payments, customer messaging, financial claims or file delivery.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import CompanyInquiry, CommerceFunnelEvent, Product


class RevenueOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="revenue_ops_owner_20261114", password="local-test-pass",
            email="owner@example.invalid",
        )
        cls.staff = get_user_model().objects.create_user(
            username="revenue_ops_staff_20261114", password="local-test-pass",
            is_staff=True,
        )
        cls.viewer = get_user_model().objects.create_user(
            username="revenue_ops_viewer_20261114", password="local-test-pass",
        )

    def setUp(self):
        self.url = reverse("command_center_revenue_operations_api")

    def _lead(self, *, kind="commercial", status="new", age_days=0):
        lead = CompanyInquiry.objects.create(
            kind=kind, status=status, name="Private Customer",
            email="customer@example.invalid", phone="do-not-echo",
            subject="Confidential customer budget",
            message="Secret data never expose",
        )
        if age_days:
            CompanyInquiry.objects.filter(pk=lead.pk).update(
                created_at=timezone.now() - timedelta(days=age_days)
            )
        return lead

    def _get(self, query=""):
        self.client.force_login(self.owner)
        return self.client.get(self.url + query)

    def test_owner_get_returns_snapshot(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent"], "mojtaba.bot.ai")
        self.assertTrue(response.json()["read_only"])

    def test_staff_without_superuser_denied(self):
        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_plain_user_denied(self):
        self.client.force_login(self.viewer)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_anonymous_denied(self):
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_post_does_not_mutate(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_no_store_and_nosniff(self):
        response = self._get()
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Pragma"], "no-cache")

    def test_empty_snapshot_keys_exist(self):
        x = self._get().json()
        self.assertEqual(x["inquiries"]["all_in_window"], 0)
        self.assertEqual(x["inquiries"]["open_backlog_all_time"], 0)
        self.assertIsNone(x["inquiries"]["oldest_open_age_days"])
        self.assertEqual(x["funnel"]["event_counts"]["payment_confirmed"], 0)

    def test_7_30_90_windows_are_supported(self):
        for days in (7, 30, 90):
            self.assertEqual(self._get(f"?days={days}").json()["window_days"], days)

    def test_unsupported_window_is_400(self):
        self.assertEqual(self._get("?days=999").status_code, 400)

    def test_bad_window_does_not_return_private_data(self):
        x = self._get("?days=999").json()
        self.assertEqual(set(x), {"error"})

    def test_statuses_counted_without_qualification_assumptions(self):
        self._lead(status="new")
        self._lead(status="reviewing")
        self._lead(status="approved")
        self._lead(status="closed")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["all_in_window"], 4)
        self.assertEqual(x["statuses"]["approved"], 1)
        self.assertIn("not_contract", x["approved_means"])

    def test_kinds_grouped(self):
        self._lead(kind="research")
        self._lead(kind="commercial")
        x = self._get().json()["inquiries"]["kinds"]
        self.assertEqual(x["research"], 1)
        self.assertEqual(x["commercial"], 1)

    def test_closed_leads_not_in_backlog(self):
        self._lead(status="closed")
        self._lead(status="reviewing")
        self.assertEqual(self._get().json()["inquiries"]["open_backlog_all_time"], 1)

    def test_old_unresolved_leads_stay_in_backlog_not_recent_window(self):
        self._lead(age_days=100, status="reviewing")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["all_in_window"], 0)
        self.assertEqual(x["open_backlog_all_time"], 1)
        self.assertGreaterEqual(x["oldest_open_age_days"], 99)

    def test_old_closed_does_not_contribute_to_backlog(self):
        self._lead(age_days=100, status="closed")
        self.assertEqual(self._get().json()["inquiries"]["open_backlog_all_time"], 0)

    def test_future_dated_leads_excluded(self):
        lead = self._lead()
        CompanyInquiry.objects.filter(pk=lead.pk).update(
            created_at=timezone.now() + timedelta(days=1)
        )
        x = self._get().json()["inquiries"]
        self.assertEqual(x["all_in_window"], 0)
        self.assertEqual(x["open_backlog_all_time"], 0)

    def test_no_customer_identifiers_in_payload(self):
        self._lead()
        txt = self._get().content.decode("utf-8")
        for secret in ("Private Customer", "customer@example.invalid", "do-not-echo",
                       "Confidential customer budget", "Secret data never expose"):
            self.assertNotIn(secret, txt)

    def test_unknown_status_recorded_not_dropped(self):
        self._lead(status="custom-undocumented")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["all_in_window"], 1)
        self.assertEqual(x["unknown_status"], 1)

    def test_marketing_events_are_not_paid_receipts(self):
        CommerceFunnelEvent.objects.create(event_name="payment_confirmed")
        CommerceFunnelEvent.objects.create(event_name="payment_confirmed")
        x = self._get().json()
        self.assertEqual(x["funnel"]["event_counts"]["payment_confirmed"], 2)
        self.assertEqual(x["funnel"]["counting_unit"], "events_not_unique_buyers")
        self.assertIsNone(x["commercial_evidence"]["externally_settled_cash"])
        self.assertIsNone(x["commercial_evidence"]["verified_net_profit"])

    def test_future_event_excluded(self):
        ev = CommerceFunnelEvent.objects.create(event_name="begin_checkout")
        CommerceFunnelEvent.objects.filter(pk=ev.pk).update(
            created_at=timezone.now() + timedelta(days=1)
        )
        self.assertEqual(self._get().json()["funnel"]["event_counts"]["begin_checkout"], 0)

    def test_unknown_event_is_not_invented_settlement(self):
        CommerceFunnelEvent.objects.create(event_name="external_settlement_trusted")
        x = self._get().json()
        self.assertEqual(x["funnel"]["unknown_events"], 1)
        self.assertIsNone(x["commercial_evidence"]["externally_settled_cash"])



    def test_unreviewed_open_count(self):
        self._lead(status="new")
        self._lead(status="new")
        self._lead(status="reviewing")
        self._lead(status="closed")
        self.assertEqual(self._get().json()["inquiries"]["unreviewed_open"], 2)

    def test_stale_lead_over_week(self):
        self._lead(status="reviewing", age_days=8)
        self._lead(status="reviewing", age_days=3)
        self.assertEqual(self._get().json()["inquiries"]["stale_open_over_7_days"], 1)

    def test_stale_lead_over_month(self):
        self._lead(status="reviewing", age_days=31)
        self._lead(status="reviewing", age_days=12)
        x = self._get().json()["inquiries"]
        self.assertEqual(x["stale_open_over_30_days"], 1)
        self.assertEqual(x["stale_open_over_7_days"], 2)

    def test_stale_closed_not_flagged_for_follow_up(self):
        self._lead(status="closed", age_days=60)
        x = self._get().json()["inquiries"]
        self.assertEqual(x["stale_open_over_30_days"], 0)

    def test_backlog_by_kind_carries_old_demand(self):
        self._lead(kind="research", age_days=50, status="reviewing")
        self._lead(kind="commercial", age_days=2, status="new")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["open_backlog_by_kind"]["research"], 1)
        self.assertEqual(x["open_backlog_by_kind"]["commercial"], 1)

    def test_backlog_by_kind_excludes_closed(self):
        self._lead(kind="research", age_days=50, status="closed")
        self.assertEqual(self._get().json()["inquiries"]["open_backlog_by_kind"]["research"], 0)

    def test_unknown_kind_retained_without_exposure(self):
        self._lead(kind="private-unlisted-field")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["unknown_kind"], 1)
        self.assertEqual(x["open_backlog_unknown_kind"], 1)

    def test_approved_percentage_is_preliminary_only(self):
        self._lead(status="approved")
        self._lead(status="new")
        x = self._get().json()["inquiries"]
        self.assertEqual(x["preliminary_approval_rate_percent"], 50)
        self.assertTrue(x["preliminary_approval_rate_is_not_conversion_rate"])

    def test_approved_percentage_undefined_when_empty(self):
        self.assertIsNone(self._get().json()["inquiries"]["preliminary_approval_rate_percent"])

    def test_robots_tag_prevents_accidental_indexing(self):
        r = self._get()
        self.assertIn("noindex", r["X-Robots-Tag"])
        self.assertEqual(r["Vary"], "Cookie")

    def test_single_agent_can_inspect_operational_aggregates(self):
        from core.economic_master_agent import EconomicMasterAgent
        self._lead(kind="research")
        x = EconomicMasterAgent().inspect_revenue_operations_readonly(days=7)
        self.assertEqual(x["agent"], "mojtaba.bot.ai")
        self.assertEqual(x["inquiries"]["kinds"]["research"], 1)

    def test_single_agent_can_cost_without_payment(self):
        from core.economic_master_agent import EconomicMasterAgent
        from core.tests.test_revenue_unit_economics_20261114 import quote
        x = EconomicMasterAgent().calculate_quote_scenario_readonly(quote())
        self.assertIsNone(x["external_cash_settlement"])

    def test_single_agent_reuses_same_service_catalogue(self):
        from core.economic_master_agent import EconomicMasterAgent
        cards = EconomicMasterAgent().list_service_drafts_readonly()
        self.assertEqual(len(cards), 6)
        self.assertTrue(all(not card["external_sale_enabled"] for card in cards))

    def test_single_agent_assesses_not_sells_service(self):
        from core.economic_master_agent import EconomicMasterAgent
        from core.service_sales_controls import REQUIRED_OFFER_EVIDENCE
        r = EconomicMasterAgent().assess_service_draft_readonly(
            "RS-01", {key: True for key in REQUIRED_OFFER_EVIDENCE}
        )
        self.assertTrue(r["internal_review_ready"])
        self.assertFalse(r["external_sale_enabled"])


class CommerceFunnelSafetyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="commerce_event_staff_20261114", password="local-test-pass",
            is_staff=True,
        )

    def setUp(self):
        self.client.force_login(self.staff)
        self.url = reverse("command_center_commerce_funnel_api")

    def test_get_is_read_only_and_nocache(self):
        x = self.client.get(self.url)
        self.assertEqual(x.status_code, 200)
        self.assertIn("no-store", x["Cache-Control"])
        self.assertIsNone(x.json()["independently_settled_cash"])

    def test_post_rejected(self):
        self.assertEqual(self.client.post(self.url, {}).status_code, 405)

    def test_events_aggregated(self):
        for _ in range(3):
            CommerceFunnelEvent.objects.create(event_name="view_item")
        self.assertEqual(self.client.get(self.url).json()["events"]["view_item"], 3)

    def test_old_events_are_excluded(self):
        event = CommerceFunnelEvent.objects.create(event_name="view_store")
        CommerceFunnelEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        self.assertEqual(self.client.get(self.url).json()["events"]["view_store"], 0)

    def test_product_ranking_bounded_to_25(self):
        for i in range(27):
            product = Product.objects.create(
                title=f"Private product {i}", product_type="book", active=False,
            )
            CommerceFunnelEvent.objects.create(event_name="view_item", product=product)
        x = self.client.get(self.url).json()
        self.assertEqual(len(x["products"]), 25)
        self.assertTrue(x["products_truncated"])

    def test_no_raw_campaign_or_buyer_pii(self):
        CommerceFunnelEvent.objects.create(
            event_name="view_item", source="sensitive_source",
            campaign="buyer_email_do_not_publish",
        )
        body = self.client.get(self.url).content.decode("utf-8")
        self.assertNotIn("buyer_email_do_not_publish", body)
        self.assertNotIn("sensitive_source", body)

    def test_event_not_unique_customer_claim(self):
        x = self.client.get(self.url).json()
        self.assertTrue(x["event_count_not_unique_buyers"])
        self.assertIsNone(x["independently_verified_delivery"])
