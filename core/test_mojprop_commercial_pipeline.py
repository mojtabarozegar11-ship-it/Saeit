"""Actual DB-derived conversion figures; quotes are not revenue."""
import io
import json
from datetime import timedelta
from django.utils import timezone
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
        self.assertEqual(p["quote_coverage_percent"], 0.0)
        self.assertEqual(p["quote_draft_coverage_percent"], 50.0)
        self.assertEqual(p["distinct_leads_with_issued_quotes"], 0)
        self.assertIsNone(p["acceptance_rate_percent"])
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
                         "Quote issuance, acceptance, payment and delivery are separate evidence stages.")


    def test_issued_quote_counts_only_after_manual_issuance_evidence(self):
        lead = self.make_lead("P-ISSUED", "blueprint")
        self.make_lead("P-OTHER", "brief")
        now = timezone.now()
        proposal = MojPropOffer(
            lead=lead, title="Private specification with commercial milestones",
            scope="Produce a properly scoped research specification with references and defined milestones.",
            amount=Decimal("80.00"), currency="USD", delivery_days=7,
            status="issued", reviewed_at=now - timedelta(hours=1),
            issued_at=now - timedelta(minutes=30),
            expires_at=now + timedelta(days=7),
        )
        proposal.full_clean()
        proposal.save()
        data = pipeline_snapshot()
        self.assertEqual(data["distinct_leads_with_issued_quotes"], 1)
        self.assertEqual(data["quote_coverage_percent"], 50.0)
        self.assertEqual(data["issued_quotes_awaiting_decision"], 1)
        self.assertEqual(data["new_leads_without_issued_quote"], 1)
        # One issued offer exists; its observed acceptance rate is zero, not unknown.
        self.assertEqual(data["acceptance_rate_percent"], 0.0)

    def test_accepted_quote_is_counted_once_and_never_revenue(self):
        lead = self.make_lead("P-ACCEPTED", "signals")
        now = timezone.now()
        proposal = MojPropOffer(
            lead=lead, title="Educational commodity research with documented methodology",
            scope="Deliver an independent educational market report with scenarios and limitations.",
            amount=Decimal("145.00"), currency="USD", delivery_days=5,
            status="accepted", reviewed_at=now - timedelta(days=3),
            issued_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=5),
            accepted_at=now - timedelta(days=1),
            acceptance_reference="signed-confirmation-ACCEPTED-01",
        )
        proposal.full_clean()
        proposal.save()
        data = pipeline_snapshot()
        self.assertEqual(data["distinct_leads_with_issued_quotes"], 1)
        self.assertEqual(data["distinct_accepted_leads"], 1)
        self.assertEqual(data["acceptance_rate_percent"], 100.0)
        self.assertIsNone(data["collected_revenue"])

    def test_expired_issued_offer_and_overdue_new_lead_are_actionable(self):
        old_lead = self.make_lead("P-OVERDUE", "audit")
        MojPropRequest.objects.filter(pk=old_lead.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        lead = self.make_lead("P-EXPIRED", "brief")
        now = timezone.now()
        proposal = MojPropOffer(
            lead=lead, title="Completed written service proposal awaiting acceptance",
            scope="Provide a dated and independently reviewed research deliverable with specified limitations.",
            amount=Decimal("55.00"), currency="USD", delivery_days=5,
            status="issued", reviewed_at=now - timedelta(days=5),
            issued_at=now - timedelta(days=4),
            expires_at=now - timedelta(days=1),
        )
        proposal.full_clean()
        proposal.save()
        data = pipeline_snapshot()
        self.assertEqual(data["new_unquoted_leads_older_than_24h"], 1)
        self.assertEqual(data["issued_quotes_expired_without_acceptance"], 1)
        self.assertEqual(data["issued_quotes_awaiting_decision"], 0)

