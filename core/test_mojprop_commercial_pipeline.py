"""Actual DB-derived conversion figures; quotes are not revenue."""
import io
import json
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from core.management.commands.mojprop_commercial_pipeline import pipeline_snapshot
from core.models import MojPropOffer, MojPropRequest, MojPropDeliveryEvidence


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
                         "Drafts, issued quotes, accepted terms, handoff records and independent payment are separate evidence stages.")


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


    def test_document_handoff_does_not_misreport_payment(self):
        lead = self.make_lead("P-REPORT-DELIVERY", "brief")
        now = timezone.now()
        offer = MojPropOffer.objects.create(
            lead=lead, title="Documented analysis handoff",
            scope="A written research document with cited sources and explicit limitations and scenarios.",
            amount=Decimal("110.00"), delivery_days=4,
            status="accepted", reviewed_at=now-timedelta(days=3),
            issued_at=now-timedelta(days=2),
            accepted_at=now-timedelta(days=1),
            expires_at=now+timedelta(days=4),
            acceptance_reference="signed-acceptance-001",
        )
        proof = MojPropDeliveryEvidence.objects.create(
            offer=offer, artifact_sha256="a"*64,
            artifact_name="private-report.pdf",
            clearance_reference="approved-service-credit",
            status="sent", handoff_reference="secure-log-123",
            handed_off_at=now-timedelta(hours=2),
        )
        p = pipeline_snapshot()
        self.assertEqual(p["handoffs_recorded"], 1)
        self.assertEqual(p["customer_acknowledgments_recorded"], 0)
        self.assertEqual(p["handoff_coverage_percent"], 100.0)
        self.assertIsNone(p["collected_revenue"])
        self.assertIsNone(p["commercial_delivery_verified"])
        proof.status="acknowledged"
        proof.acknowledged_at=now-timedelta(hours=1)
        proof.acknowledgment_reference="client-confirmation-123"
        proof.full_clean()
        proof.save()
        self.assertEqual(pipeline_snapshot()["customer_acknowledgments_recorded"], 1)


    def test_forged_draft_issuance_timestamp_does_not_inflate_funnel(self):
        lead = self.make_lead("P-DRAFT-FAKE", "brief")
        now = timezone.now()
        MojPropOffer.objects.create(
            lead=lead, title="Unissued draft", scope="Private documentation pending review " * 4,
            amount=Decimal("100.00"), status="draft",
            issued_at=now, reviewed_at=now,
        )
        snapshot = pipeline_snapshot()
        self.assertEqual(snapshot["distinct_leads_with_issued_quotes"], 0)
        self.assertEqual(snapshot["quote_coverage_percent"], 0.0)

    def test_accepted_row_without_customer_reference_is_not_conversion(self):
        lead = self.make_lead("P-ACCEPT-FAKE", "signals")
        now = timezone.now()
        MojPropOffer.objects.create(
            lead=lead, title="Not verified", scope="Dated research evidence " * 4,
            amount=Decimal("120.00"), status="accepted",
            reviewed_at=now - timedelta(days=3),
            issued_at=now - timedelta(days=2),
            accepted_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=2),
            acceptance_reference="",
        )
        snapshot = pipeline_snapshot()
        self.assertEqual(snapshot["distinct_leads_with_issued_quotes"], 1)
        self.assertEqual(snapshot["distinct_accepted_leads"], 0)
        self.assertEqual(snapshot["acceptance_rate_percent"], 0.0)

    def test_handoff_without_clearance_or_reference_never_counts_as_delivery(self):
        lead = self.make_lead("P-HANDOFF-FAKE", "brief")
        now = timezone.now()
        offer = MojPropOffer.objects.create(
            lead=lead, title="Accepted scope", scope="Dated documented research " * 4,
            amount=Decimal("100.00"), status="accepted",
            reviewed_at=now - timedelta(days=3),
            issued_at=now - timedelta(days=2),
            accepted_at=now - timedelta(days=1),
            acceptance_reference="buyer-signed-111",
            expires_at=now + timedelta(days=2),
        )
        MojPropDeliveryEvidence.objects.create(
            offer=offer, artifact_sha256="a" * 64,
            artifact_name="ready.pdf", status="acknowledged",
            handoff_reference="", clearance_reference="",
            handed_off_at=now - timedelta(hours=2),
            acknowledged_at=now - timedelta(hours=1),
            acknowledgment_reference="buyer-claims-it-111",
        )
        snapshot = pipeline_snapshot()
        self.assertEqual(snapshot["distinct_accepted_leads"], 1)
        self.assertEqual(snapshot["handoffs_recorded"], 0)
        self.assertEqual(snapshot["customer_acknowledgments_recorded"], 0)
        self.assertEqual(snapshot["handoff_coverage_percent"], 0.0)

    def test_quote_version_count_is_not_mislabeled_as_unique_buyer_count(self):
        lead = self.make_lead("P-QUOTE-VERSIONS", "brief")
        now = timezone.now()
        for version in (1, 2):
            MojPropOffer.objects.create(
                lead=lead, version=version, title="Accepted scoped research",
                scope="Documented research with clearly defined milestones." * 2,
                amount=Decimal("100.00"), status="accepted",
                reviewed_at=now - timedelta(days=3),
                issued_at=now - timedelta(days=2),
                accepted_at=now - timedelta(days=1),
                acceptance_reference=f"buyer-accepts-version-{version}",
                expires_at=now + timedelta(days=1),
            )
        report = pipeline_snapshot()
        self.assertEqual(report["distinct_accepted_leads"], 1)
        self.assertEqual(report["distinct_accepted_quotes"], 2)
        self.assertEqual(report["acceptance_rate_percent"], 100.0)
        self.assertIsNone(report["collected_revenue"])

    def test_dispatch_cannot_count_without_independent_customer_acceptance(self):
        lead = self.make_lead("P-UNSIGNED-HANDOFF", "audit")
        now = timezone.now()
        offer = MojPropOffer.objects.create(
            lead=lead, title="Private research delivery",
            scope="A documented deliverable with sources and scope." * 2,
            amount=Decimal("100.00"), status="accepted",
            reviewed_at=now - timedelta(days=3),
            issued_at=now - timedelta(days=2),
            accepted_at=now - timedelta(days=1),
            acceptance_reference="",
            expires_at=now + timedelta(days=2),
        )
        MojPropDeliveryEvidence.objects.create(
            offer=offer, artifact_sha256="a" * 64,
            artifact_name="document.pdf", status="acknowledged",
            clearance_reference="internal-credit-001",
            handoff_reference="dispatch-001",
            handed_off_at=now - timedelta(hours=2),
            acknowledgment_reference="customer-claimed-001",
            acknowledged_at=now - timedelta(hours=1),
        )
        report = pipeline_snapshot()
        self.assertEqual(report["distinct_accepted_leads"], 0)
        self.assertEqual(report["distinct_accepted_quotes"], 0)
        self.assertEqual(report["handoffs_recorded"], 0)
        self.assertEqual(report["customer_acknowledgments_recorded"], 0)
        self.assertIsNone(report["collected_revenue"])

    def test_spoofed_acceptance_timestamps_do_not_count_as_conversion(self):
        now = timezone.now()
        for number, accepted_at in enumerate((
            now - timedelta(days=4), now + timedelta(days=1),
            now + timedelta(days=8),
        )):
            lead = self.make_lead(f"FAKE-ACCEPT-{number}", "signals")
            MojPropOffer.objects.create(
                lead=lead, title="Recorded research proposal",
                scope="A well-scoped educational market report with provenance and limitations.",
                amount=Decimal("90.00"), currency="USD", delivery_days=5,
                status="accepted", reviewed_at=now - timedelta(days=3),
                issued_at=now - timedelta(days=2),
                expires_at=now + timedelta(days=5),
                accepted_at=accepted_at,
                acceptance_reference="unverified-user-acceptance",
            )
        report = pipeline_snapshot()
        self.assertEqual(report["distinct_leads_with_issued_quotes"], 3)
        self.assertEqual(report["distinct_accepted_leads"], 0)
        self.assertEqual(report["acceptance_rate_percent"], 0.0)

    def test_unconsented_persisted_offer_is_excluded_from_conversion_kpis(self):
        now = timezone.now()
        lead = self.make_lead("UNCONSENTED-ISSUED", "brief")
        MojPropOffer.objects.create(
            lead=lead, title="Unconsented quote",
            scope="A dated independent research report with scope and limitations.",
            amount=Decimal("99.00"), currency="USD", delivery_days=7,
            status="issued", reviewed_at=now - timedelta(hours=2),
            issued_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=2),
        )
        MojPropRequest.objects.filter(pk=lead.pk).update(consent=False)
        report = pipeline_snapshot()
        self.assertEqual(report["total_inquiries"], 1)
        self.assertEqual(report["distinct_leads_with_issued_quotes"], 0)
        self.assertIsNone(report["acceptance_rate_percent"])

    def test_handoff_record_before_acceptance_does_not_inflate_delivery(self):
        now = timezone.now()
        lead = self.make_lead("BAD-HANDOFF-TIME", "brief")
        offer = MojPropOffer.objects.create(
            lead=lead, title="Validated quotation",
            scope="A properly reviewed report with verifiable source evidence and limits.",
            amount=Decimal("80.00"), currency="USD", delivery_days=7,
            status="accepted", reviewed_at=now-timedelta(days=4),
            issued_at=now-timedelta(days=3),
            accepted_at=now-timedelta(days=2),
            expires_at=now+timedelta(days=3),
            acceptance_reference="independent-acceptance-01",
        )
        MojPropDeliveryEvidence.objects.create(
            offer=offer, artifact_sha256="f"*64,
            artifact_name="research.pdf", status="sent",
            clearance_reference="owner-approved-credit",
            handoff_reference="receipt-old-evidence",
            handed_off_at=now-timedelta(days=5),
        )
        report = pipeline_snapshot()
        self.assertEqual(report["distinct_accepted_leads"], 1)
        self.assertEqual(report["handoffs_recorded"], 0)
        self.assertEqual(report["handoff_coverage_percent"], 0.0)
