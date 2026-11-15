"""Offer lifecycle integrity: status labels cannot manufacture paid services."""
from datetime import timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from core.models import MojPropRequest, MojPropOffer


class OfferStatusTransitionTests(TestCase):
    def setUp(self):
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-0A01B202", name="Market buyer",
            email="buyer@example.org", route="brief", horizon="week",
            notes="I need a professionally sourced market brief for education.",
            consent=True,
        )
        self.past = timezone.now() - timedelta(hours=1)
        self.offer = MojPropOffer.objects.create(
            lead=self.lead, version=1, title="Gold research report",
            scope="A five-page report with dated source references, invalidation, risk and market scenarios.",
            amount=Decimal("100.00"), currency="USD", delivery_days=7,
        )

    def move(self, status, **changes):
        self.offer.refresh_from_db()
        self.offer.status = status
        for k,v in changes.items():
            setattr(self.offer,k,v)
        self.offer.full_clean()
        self.offer.save()

    def test_draft_cannot_skip_reviewed_issuance_lifecycle(self):
        with self.assertRaises(ValidationError):
            self.move("issued", reviewed_at=self.past,
                      issued_at=self.past, expires_at=self.past+timedelta(days=2))
        self.move("approved", reviewed_at=self.past)
        self.move("issued", issued_at=self.past, expires_at=self.past+timedelta(days=2))
        self.assertEqual(self.offer.status, "issued")

    def test_active_quote_cannot_be_reverted_to_unreviewed_state(self):
        self.move("approved", reviewed_at=self.past)
        self.move("issued", issued_at=self.past, expires_at=self.past+timedelta(days=2))
        with self.assertRaises(ValidationError):
            self.move("draft")
        with self.assertRaises(ValidationError):
            self.move("approved")

    def test_cancelled_quote_cannot_be_revived_or_repriced(self):
        self.move("cancelled")
        self.offer.refresh_from_db()
        self.offer.amount=Decimal("1.00")
        with self.assertRaises(ValidationError):
            self.offer.full_clean()
        for target in ("draft", "approved", "issued", "accepted"):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                self.move(target, reviewed_at=self.past,
                          issued_at=self.past, expires_at=self.past+timedelta(days=2),
                          accepted_at=timezone.now(),
                          acceptance_reference="manually verified consent")

    def test_issued_quote_requires_expiry_after_issuance(self):
        with self.assertRaises(ValidationError):
            self.move("issued", reviewed_at=self.past,
                      issued_at=self.past + timedelta(minutes=2),
                      expires_at=self.past + timedelta(minutes=1))
