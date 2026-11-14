"""End-to-end operator CLI tests; no customer PII export or outbound message."""
import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.company_inquiry_models import CompanyInquiry


class LeadOperatorCommandsTests(TestCase):
    def _output(self, command, **kwargs):
        output = StringIO()
        call_command(command, stdout=output, **kwargs)
        return json.loads(output.getvalue())

    def _lead(self, kind="project"):
        return CompanyInquiry.objects.create(
            kind=kind, name="Sensitive operator customer",
            email="secret@example.invalid", status="new",
            subject="[AGR-01] Sensitive topic",
            message="Sensitive details for economic analysis.",
        )

    def test_lead_queue_command_returns_empty_without_database_error(self):
        data = self._output("mojtaba_lead_queue_readonly")
        self.assertEqual(data["items"], [])
        self.assertEqual(data["matching_open_requests"], 0)

    def test_lead_queue_command_reuses_single_bot_identity(self):
        self._lead()
        data = self._output("mojtaba_lead_queue_readonly")
        self.assertEqual(data["agent"], "mojtaba.bot.ai")
        self.assertEqual(data["matching_open_requests"], 1)

    def test_lead_queue_command_never_exports_contact_pii(self):
        self._lead()
        body = json.dumps(self._output("mojtaba_lead_queue_readonly"))
        self.assertNotIn("secret@example.invalid", body)
        self.assertNotIn("Sensitive operator customer", body)

    def test_lead_queue_supports_kind_filter(self):
        self._lead(kind="research")
        self._lead(kind="commercial")
        data = self._output("mojtaba_lead_queue_readonly", kind="research")
        self.assertEqual(data["matching_open_requests"], 1)
        self.assertEqual(data["items"][0]["kind"], "research")

    def test_lead_queue_bad_page_returns_command_error(self):
        with self.assertRaises(CommandError):
            self._output("mojtaba_lead_queue_readonly", page=101)

    def test_lead_queue_does_not_change_status(self):
        lead = self._lead()
        self._output("mojtaba_lead_queue_readonly")
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")

    def test_offer_catalogue_cli_has_six_service_cards(self):
        data = self._output("mojtaba_offer_catalog_readonly")
        self.assertEqual(len(data["services"]), 6)
        self.assertEqual(data["agent"], "mojtaba.bot.ai")

    def test_offer_catalogue_cli_filters_one_service(self):
        data = self._output("mojtaba_offer_catalog_readonly", service_code="RS-01")
        self.assertEqual(len(data["services"]), 1)
        self.assertEqual(data["services"][0]["service_code"], "RS-01")

    def test_offer_catalogue_cli_cannot_claim_sellable_price(self):
        data = self._output("mojtaba_offer_catalog_readonly")
        for row in data["services"]:
            self.assertIsNone(row["price"])
            self.assertFalse(row["external_sale_enabled"])

    def test_offer_catalogue_cli_never_makes_revenue_claim(self):
        data = self._output("mojtaba_offer_catalog_readonly")
        self.assertIsNone(data["verified_cash"])
        self.assertEqual(data["source_status"], "DRAFT_NONBINDING_NO_EXTERNAL_SALE")
