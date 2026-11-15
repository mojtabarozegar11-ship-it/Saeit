"""Actual DB-derived conversion figures; quotes are not revenue."""
import io
import json
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from core.management.commands.mojprop_commercial_pipeline import pipeline_snapshot
from core.models import MojPropOffer, MojPropRequest


class PipelineReportingTests(TestCase):
    def make_lead(self, ref, route, status="new", product_id=None):
        return MojPropRequest.objects.create(
            request_id=ref, name="Buyer", email=ref.lower()+"@example.org",
            route=route, horizon="week", notes="Describe a real private research delivery request.",
            consent=True, source="moj-prop-public", status=status,
            product_id=product_id,
        )

    def test_empty_pipeline_does_not_fabricate_revenue_or_percentages(self):
        p = pipeline_snapshot()
        self.assertEqual(p["total_inquiries"], 0)
        self.assertIsNone(p["quote_coverage_percent"])
        self.assertIsNone(p["acceptance_rate_percent"])
        self.assertIsNone(p["collected_revenue"])
        self.assertIsNone(p["payments_independently_verified"])
        self.assertIsNone(p["commercial_delivery_verified"])

    def test_counts_distinct_buyer_leads_not_negotiated_quote_versions(self):
        a = self.make_lead("MPROP-001", "signals")
        self.make_lead("MPROP-002", "digital", "reviewing", 72)
        for version in (1, 2):
            MojPropOffer.objects.create(
                lead=a, version=version,
                title="Research service", amount=Decimal("100.00"),
                scope="Produce a dated educational briefing containing sources, scenario and limitations.",
                status="draft", currency="USD", delivery_days=5,
            )
        p = pipeline_snapshot()
        self.assertEqual(p["total_inquiries"], 2)
        self.assertEqual(p["distinct_leads_with_quotes"], 1)
        self.assertEqual(p["quote_coverage_percent"], 50.0)
        self.assertEqual(p["product_specific_inquiries"], 1)
        self.assertEqual(p["quotes_by_status"]["draft"], 2)
        self.assertIsNone(p["collected_revenue"])

    def test_cli_emits_private_aggregate_json_not_customer_identifiers(self):
        lead = self.make_lead("MPRIV-SECRET-001", "brief")
        dest = io.StringIO()
        call_command("mojprop_commercial_pipeline", stdout=dest)
        content = dest.getvalue()
        report = json.loads(content)
        self.assertEqual(report["total_inquiries"], 1)
        self.assertEqual(report["inquiries_by_route"]["brief"], 1)
        self.assertNotIn(lead.request_id, content)
        self.assertNotIn(lead.email, content)
        self.assertEqual(report["scope_note"],
                         "Quote acceptance is not payment, delivery, or realized income.")
