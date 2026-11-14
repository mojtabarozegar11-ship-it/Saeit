"""C04 source-of-truth release gate and owner-only diagnostic tests.

All tests are isolated and never hit PHP/cPanel, customer data or external mail.
"""
import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.company_inquiry_models import CompanyInquiry
from core.service_intake_routing import (
    EXPECTED_SOURCE, LEGACY_INQUIRY_PATH, django_service_intake_active,
    service_contact_card, service_contact_url, service_intake_source_snapshot,
)
from core.service_sales_controls import SERVICE_CARDS


ENABLED = {
    "DEBUG": True,
    "SERVICE_INTAKE_DJANGO_ENABLED": True,
    "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED": True,
    "SERVICE_INTAKE_ROLLBACK_VERIFIED": True,
    "SERVICE_INTAKE_PRIVACY_REVIEWED": True,
    "SERVICE_INTAKE_SOURCE_OF_TRUTH": EXPECTED_SOURCE,
}
DISABLED = {**ENABLED, "SERVICE_INTAKE_DJANGO_ENABLED": False}


@override_settings(**DISABLED)
class DefaultSourceOfTruthTests(TestCase):
    def setUp(self):
        self.url = reverse("service_inquiry", args=["AGR-01"])
        self.payload = {
            "name": "Sensitive Buyer", "email": "buyer@example.invalid",
            "subject": "Farm service inquiry",
            "message": "A legitimate long enquiry about costs, capacity, and timing.",
            "consent": "on", "website": "",
        }

    def test_disabled_django_is_not_primary(self):
        self.assertFalse(django_service_intake_active())

    def test_legacy_path_exact_and_not_external(self):
        self.assertEqual(LEGACY_INQUIRY_PATH, "/ask-master/index.php?service=1")
        self.assertTrue(LEGACY_INQUIRY_PATH.startswith("/"))
        self.assertNotIn("://", LEGACY_INQUIRY_PATH)

    def test_all_six_offers_choose_one_existing_fallback(self):
        for code in SERVICE_CARDS:
            self.assertEqual(service_contact_url(code), LEGACY_INQUIRY_PATH)

    def test_disabled_direct_django_get_redirects_to_legacy(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], LEGACY_INQUIRY_PATH)

    def test_disabled_django_get_has_no_store(self):
        self.assertIn("no-store", self.client.get(self.url)["Cache-Control"])

    def test_disabled_direct_django_post_is_not_forwarded(self):
        response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Location", response)
        self.assertEqual(response["Retry-After"], "3600")

    def test_disabled_post_has_not_stored_any_lead(self):
        self.client.post(self.url, self.payload)
        self.assertEqual(CompanyInquiry.objects.count(), 0)

    def test_disabled_post_does_not_make_acknowledgement(self):
        response = self.client.post(self.url, self.payload)
        self.assertNotIn("دریافت شد", response.content.decode("utf-8"))

    def test_disabled_post_private_and_noindex(self):
        response = self.client.post(self.url, self.payload)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_nonexistent_service_fails_closed_even_when_disabled(self):
        response = self.client.get(reverse("service_inquiry", args=["NO-01"]))
        self.assertEqual(response.status_code, 404)

    def test_services_page_has_six_old_source_links(self):
        result = self.client.get(reverse("services"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context["service_offers"][0]["contact_url"], LEGACY_INQUIRY_PATH)
        self.assertEqual(len(result.context["service_offers"]), 6)

    def test_services_page_has_no_active_django_links(self):
        text = self.client.get(reverse("services")).content.decode("utf-8")
        for code in SERVICE_CARDS:
            self.assertNotIn(reverse("service_inquiry", args=[code]), text)

    def test_disabled_status_does_not_claim_legacy_live_is_healthy(self):
        d = service_intake_source_snapshot()
        self.assertEqual(d["routing_mode"], "legacy_ask_master_unverified")
        self.assertIsNone(d["live_php_form_verified"])
        self.assertIsNone(d["real_revenue_collected"])

    def test_unknown_service_is_not_redirected(self):
        with self.assertRaises(ValueError):
            service_contact_url("MALICIOUS")

    def test_nonstring_code_rejected(self):
        with self.assertRaises(ValueError):
            service_contact_url(1)

    def test_draft_card_never_creates_price_or_sale(self):
        card = service_contact_card("RS-01")
        self.assertFalse(card["contract_active"])
        self.assertFalse(card["customer_payment_taken"])
        self.assertFalse(card["prices_approved"])


@override_settings(**ENABLED)
class FourGateApprovalTests(TestCase):
    def test_all_gates_and_exact_source_enable_django_intake(self):
        self.assertTrue(django_service_intake_active())

    def test_django_url_only_when_all_gates_enabled(self):
        self.assertEqual(
            service_contact_url("RS-02"),
            reverse("service_inquiry", args=["RS-02"]),
        )

    def test_new_django_page_readable_only_when_enabled(self):
        self.assertEqual(
            self.client.get(reverse("service_inquiry", args=["RS-02"])).status_code, 200
        )

    def test_services_page_cta_switches_with_gate(self):
        response = self.client.get(reverse("services"))
        self.assertIn(
            reverse("service_inquiry", args=["SEO-01"]),
            response.content.decode("utf-8"),
        )

    def test_disabled_flag_blocks_route_even_with_other_three(self):
        for key in (
            "SERVICE_INTAKE_DJANGO_ENABLED",
            "SERVICE_INTAKE_SINGLE_SOURCE_APPROVED",
            "SERVICE_INTAKE_ROLLBACK_VERIFIED",
            "SERVICE_INTAKE_PRIVACY_REVIEWED",
        ):
            with override_settings(**{key: False}):
                self.assertFalse(django_service_intake_active(), key)
                self.assertEqual(service_contact_url("RS-01"), LEGACY_INQUIRY_PATH)

    def test_string_true_does_not_bypass_flag(self):
        with override_settings(SERVICE_INTAKE_DJANGO_ENABLED="true"):
            self.assertFalse(django_service_intake_active())

    def test_integer_one_does_not_bypass_flag(self):
        with override_settings(SERVICE_INTAKE_DJANGO_ENABLED=1):
            self.assertFalse(django_service_intake_active())

    def test_unexpected_source_blocks_even_with_four_true(self):
        with override_settings(SERVICE_INTAKE_SOURCE_OF_TRUTH="php"):
            self.assertFalse(django_service_intake_active())

    def test_empty_source_blocks(self):
        with override_settings(SERVICE_INTAKE_SOURCE_OF_TRUTH=""):
            self.assertFalse(django_service_intake_active())

    def test_false_rollback_blocks_post_and_does_not_store(self):
        with override_settings(SERVICE_INTAKE_ROLLBACK_VERIFIED=False):
            response = self.client.post(reverse("service_inquiry", args=["AGR-01"]), {
                "name": "Farmer Person", "email": "farmer@example.invalid",
                "subject": "Farm unit report",
                "message": "I am requesting a complete economic and yield study.",
                "consent": "on", "website": "",
            })
        self.assertEqual(response.status_code, 503)
        self.assertFalse(CompanyInquiry.objects.exists())

    def test_true_status_still_does_not_claim_external_certification(self):
        d = service_intake_source_snapshot()
        self.assertTrue(d["django_new_leads_enabled"])
        self.assertIsNone(d["live_django_db_verified"])
        self.assertIsNone(d["live_cross_system_reconciliation"])
        self.assertFalse(d["production_release_authorized_by_this_report"])


@override_settings(**DISABLED)
class IntakeDiagnosticsApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_superuser(
            "lead_source_owner_c04", "owner@example.invalid", "local-pass"
        )
        cls.staff = users.objects.create_user(
            "lead_source_staff_c04", password="local-pass", is_staff=True
        )
        cls.viewer = users.objects.create_user(
            "lead_source_viewer_c04", password="local-pass"
        )

    def setUp(self):
        self.path = reverse("command_center_service_intake_source_api")

    def _get(self):
        self.client.force_login(self.owner)
        return self.client.get(self.path)

    def test_owner_reads_single_bot_snapshot(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["agent"], "mojtaba.bot.ai")

    def test_anonymous_is_not_authorized(self):
        self.assertNotEqual(self.client.get(self.path).status_code, 200)

    def test_staff_cannot_read_owner_configuration(self):
        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get(self.path).status_code, 200)

    def test_viewer_denied(self):
        self.client.force_login(self.viewer)
        self.assertNotEqual(self.client.get(self.path).status_code, 200)

    def test_post_not_permitted(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.path).status_code, 405)

    def test_no_store_noindex_vary_on_snapshot(self):
        resp = self._get()
        self.assertIn("no-store", resp["Cache-Control"])
        self.assertIn("noindex", resp["X-Robots-Tag"])
        self.assertEqual(resp["Vary"], "Cookie")

    def test_snapshot_contains_no_credentials_or_user_pii(self):
        text = self._get().content.decode()
        self.assertNotIn("owner@example.invalid", text)
        self.assertNotIn("local-pass", text)
        self.assertNotIn("secret_key", text.lower())

    def test_snapshot_flags_are_boolean_only(self):
        d = self._get().json()
        for value in d["django_gate_flags"].values():
            self.assertIs(type(value), bool)

    def test_snapshot_reports_correct_service_count(self):
        self.assertEqual(self._get().json()["authoritative_catalogue_count"], 6)

    def test_snapshot_never_claims_paid_settlement(self):
        self.assertIsNone(self._get().json()["real_revenue_collected"])

    def test_owner_cli_reports_same_canonical_routing(self):
        s = StringIO()
        call_command("mojtaba_intake_source_readonly", stdout=s)
        data = json.loads(s.getvalue())
        self.assertEqual(data["fallback_path"], LEGACY_INQUIRY_PATH)
        self.assertFalse(data["django_new_leads_enabled"])

    def test_agent_inspects_same_configuration(self):
        from core.economic_master_agent import EconomicMasterAgent
        d = EconomicMasterAgent().inspect_intake_source_configuration_readonly()
        self.assertEqual(d["agent"], "mojtaba.bot.ai")
        self.assertEqual(d["routing_mode"], "legacy_ask_master_unverified")

    def test_snapshot_creates_no_customer_record(self):
        self._get()
        self.assertEqual(CompanyInquiry.objects.count(), 0)
