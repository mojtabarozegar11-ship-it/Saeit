"""Commercial conversion, quote integrity and no-automatic-payment safeguards."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import MojPropRequest, MojPropOffer


class MojPropOfferTests(TestCase):
    def setUp(self):
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-FADEBEEF",
            name="Service buyer", email="buyer@example.org",
            route="signals", horizon="week",
            notes="A dated market-brief proposal with educational scope and risk.",
            consent=True, source="moj-prop-public",
        )

    def offer(self, **kwargs):
        data = {
            "lead": self.lead,
            "title": "Private educational gold research brief",
            "scope": "Deliver a written gold research brief with dated sources, scenario analysis, invalidation and limitations.",
            "amount": Decimal("125.00"),
            "currency": "USD",
            "delivery_days": 5,
        }
        data.update(kwargs)
        return MojPropOffer(**data)

    def test_valid_quote_is_durable_and_not_payment(self):
        offer = self.offer()
        offer.full_clean()
        offer.save()
        self.assertEqual(offer.status, "draft")
        self.assertEqual(MojPropOffer.objects.get(lead=self.lead).amount, Decimal("125.00"))
        self.assertIn("NOT A PAYMENT INVOICE", offer.manual_quote_text)
        self.assertIn("MOJPROP-20261115-FADEBEEF", offer.manual_quote_text)
        self.assertIn("No payment has been collected", offer.manual_quote_text)
        self.assertNotIn("Wallet address", offer.manual_quote_text)

    def test_quote_must_have_positive_exact_price(self):
        for value in (
            Decimal("0"), Decimal("-10"), Decimal("1.001"),
            Decimal("NaN"), Decimal("Infinity"), Decimal("12.9999"),
        ):
            with self.subTest(value=str(value)), self.assertRaises(ValidationError):
                self.offer(amount=value).full_clean()

    def test_draft_requires_real_scope_and_title(self):
        for override in ({"title": ""}, {"scope": "too short"}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                self.offer(**override).full_clean()

    def test_active_offer_requires_review_and_issuance_evidence(self):
        for state in ("approved", "issued", "accepted"):
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self.offer(status=state).full_clean()

    def test_manual_issuance_requires_review_and_expiry(self):
        moment = timezone.now()
        good = self.offer(
            status="issued", reviewed_at=moment,
            issued_at=moment, expires_at=moment + timedelta(days=7),
        )
        good.full_clean()
        good.save()
        self.assertEqual(MojPropOffer.objects.count(), 1)

        stale = self.offer(
            status="issued", reviewed_at=moment,
            issued_at=moment, expires_at=moment - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            stale.full_clean()

    def test_one_lead_can_only_have_one_quote(self):
        first = self.offer()
        first.full_clean()
        first.save()
        with self.assertRaises(ValidationError):
            self.offer(amount=Decimal("160.00")).full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.offer(amount=Decimal("160.00")).save()

    def test_delivery_days_cannot_be_infinite_or_zero(self):
        for value in (0, 91, -1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.offer(delivery_days=value).full_clean()

    def test_offer_does_not_change_lead_to_delivered_or_paid(self):
        offer = self.offer()
        offer.full_clean()
        offer.save()
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "new")
        self.assertFalse(hasattr(offer, "receipt_id"))
        self.assertFalse(hasattr(offer, "payment_hash"))
