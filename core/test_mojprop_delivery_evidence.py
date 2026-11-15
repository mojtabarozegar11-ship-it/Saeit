"""A verifiable private deliverable must progress through handoff and receipt."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import MojPropDeliveryEvidence, MojPropOffer, MojPropRequest


class DeliveryEvidenceTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-BEEF0077", name="Private buyer",
            email="buyer@example.org", route="brief", horizon="week",
            notes="An educational market research report with sources and risk.",
            consent=True,
        )
        self.quote = MojPropOffer.objects.create(
            lead=self.lead, version=1, status="accepted",
            title="Written research report",
            scope="Prepare a private dated research report with complete citations, limitations and invalidation cases.",
            amount=Decimal("100.00"), delivery_days=7,
            reviewed_at=self.now-timedelta(hours=3),
            issued_at=self.now-timedelta(hours=2),
            expires_at=self.now+timedelta(days=3),
            accepted_at=self.now-timedelta(hours=1),
            acceptance_reference="signed-order:buyer-consent-record",
        )
        self.digest = "a" * 64

    def item(self, **changes):
        params = dict(offer=self.quote, artifact_name="market-report-v1.pdf",
                      artifact_sha256=self.digest)
        params.update(changes)
        return MojPropDeliveryEvidence(**params)

    def test_private_report_prepared_is_not_delivery(self):
        proof = self.item()
        proof.full_clean()
        proof.save()
        self.assertEqual(proof.status, "prepared")
        self.assertIsNone(proof.handed_off_at)
        self.assertIsNone(proof.acknowledged_at)

    def test_sent_requires_clearance_reference_and_actual_handoff(self):
        with self.assertRaises(ValidationError):
            self.item(status="sent").full_clean()
        handoff = self.now-timedelta(minutes=15)
        proof = self.item(
            status="sent", handed_off_at=handoff,
            clearance_reference="contract-credit:approved-service-terms",
            handoff_reference="secure-delivery:client-portal-log",
        )
        proof.full_clean()
        proof.save()
        self.assertEqual(proof.status, "sent")
        self.assertIsNone(proof.acknowledged_at)

    def test_acknowledgement_requires_customer_evidence(self):
        handoff = self.now-timedelta(minutes=15)
        proof = self.item(
            status="acknowledged", handed_off_at=handoff,
            clearance_reference="verified-contract-terms",
            handoff_reference="delivery-log:ABC",
        )
        with self.assertRaises(ValidationError):
            proof.full_clean()
        proof.acknowledgment_reference = "client-portal:ack-abc"
        proof.acknowledged_at = self.now-timedelta(minutes=5)
        proof.full_clean()
        proof.save()
        self.assertEqual(proof.status, "acknowledged")

    def test_issued_delivery_cannot_be_replaced_or_reverted(self):
        t = self.now-timedelta(minutes=20)
        proof = self.item(
            status="sent", handed_off_at=t,
            clearance_reference="contract-paid-or-credit-note-abc",
            handoff_reference="secure-handoff:case-99",
        )
        proof.full_clean()
        proof.save()
        proof.artifact_sha256 = "b"*64
        with self.assertRaises(ValidationError):
            proof.full_clean()
        proof.refresh_from_db()
        proof.status="prepared"
        with self.assertRaises(ValidationError):
            proof.full_clean()
        proof.refresh_from_db()
        proof.status="acknowledged"
        proof.acknowledged_at=self.now-timedelta(minutes=1)
        proof.acknowledgment_reference="buyer-confirmation-99"
        proof.full_clean()
        proof.save()

    def test_future_or_backdated_acknowledgement_is_rejected(self):
        t = self.now-timedelta(minutes=10)
        proof = self.item(
            status="acknowledged", handed_off_at=t,
            clearance_reference="legal-credit-approved",
            handoff_reference="secure-handoff-01",
            acknowledgment_reference="customer-signed-01",
            acknowledged_at=t-timedelta(seconds=1),
        )
        with self.assertRaises(ValidationError):
            proof.full_clean()
        proof.acknowledged_at=self.now+timedelta(days=1)
        with self.assertRaises(ValidationError):
            proof.full_clean()

    def test_no_unaccepted_offer_or_fake_checksum(self):
        self.quote.status="issued"
        self.quote.save(update_fields=["status"])
        for digest in ("0"*64, "g"*64, "a"*63, "", "A"*64):
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                self.item(artifact_sha256=digest).full_clean()
        with self.assertRaises(ValidationError):
            self.item().full_clean()
