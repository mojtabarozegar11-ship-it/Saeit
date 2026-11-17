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

    def test_same_lead_and_version_cannot_be_duplicated(self):
        first = self.offer()
        first.full_clean()
        first.save()
        with self.assertRaises(ValidationError):
            self.offer(amount=Decimal("160.00")).full_clean()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.offer(amount=Decimal("160.00")).save()

    def test_new_version_is_separate_not_overwriting_accepted_terms(self):
        previous = self.offer()
        previous.full_clean()
        previous.save()
        second = self.offer(version=2, amount=Decimal("135.00"))
        second.full_clean()
        second.save()
        self.assertEqual(MojPropOffer.objects.filter(lead=self.lead).count(), 2)
        previous.refresh_from_db()
        self.assertEqual(previous.amount, Decimal("125.00"))
        self.assertIn("version 2", second.manual_quote_text)

    def test_issued_offer_is_immutable_and_can_only_be_superseded(self):
        issued = timezone.now() - timedelta(hours=1)
        offer = self.offer(
            status="issued", reviewed_at=issued,
            issued_at=issued, expires_at=issued + timedelta(days=7),
        )
        offer.full_clean()
        offer.save()
        offer.amount = Decimal("1.00")
        with self.assertRaises(ValidationError):
            offer.full_clean()
        offer.refresh_from_db()
        self.assertEqual(offer.amount, Decimal("125.00"))
        offer.status = "draft"
        with self.assertRaises(ValidationError):
            offer.full_clean()
        offer.refresh_from_db()
        offer.status = "accepted"
        offer.accepted_at = issued + timedelta(minutes=3)
        offer.acceptance_reference = "signed-approval:manual-case-FADEBEEF"
        offer.full_clean()
        offer.save(update_fields=["status", "accepted_at", "acceptance_reference"])
        self.assertEqual(offer.status, "accepted")

    def test_acceptance_requires_a_real_reference_and_valid_time(self):
        issued = timezone.now() - timedelta(hours=1)
        quote = self.offer(
            status="issued", reviewed_at=issued,
            issued_at=issued, expires_at=issued + timedelta(days=5),
        )
        quote.full_clean()
        quote.save()
        quote.status = "accepted"
        with self.assertRaises(ValidationError):
            quote.full_clean()
        quote.acceptance_reference = "signed-contract:ACCEPT-20261115"
        quote.accepted_at = issued - timedelta(minutes=1)
        with self.assertRaises(ValidationError):
            quote.full_clean()
        quote.accepted_at = issued + timedelta(days=6)
        with self.assertRaises(ValidationError):
            quote.full_clean()
        quote.accepted_at = timezone.now() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            quote.full_clean()
        quote.accepted_at = timezone.now()
        quote.full_clean()
        quote.save()
        self.assertEqual(quote.status, "accepted")
        self.assertIn("Proposal status: accepted", quote.manual_quote_text)

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


    def test_review_and_issuance_timestamps_cannot_be_in_future(self):
        now = timezone.now()
        cases = [
            dict(status="approved", reviewed_at=now + timedelta(hours=1)),
            dict(status="issued", reviewed_at=now - timedelta(minutes=2),
                 issued_at=now + timedelta(hours=1),
                 expires_at=now + timedelta(days=3)),
            dict(status="issued", reviewed_at=now + timedelta(hours=1),
                 issued_at=now, expires_at=now + timedelta(days=3)),
        ]
        for params in cases:
            with self.subTest(params=params), self.assertRaises(ValidationError):
                self.offer(**params).full_clean()

    def test_offer_may_not_be_issued_before_manual_review(self):
        now = timezone.now()
        with self.assertRaises(ValidationError):
            self.offer(status="issued", reviewed_at=now - timedelta(minutes=5),
                       issued_at=now - timedelta(minutes=10),
                       expires_at=now + timedelta(days=4)).full_clean()

    def test_unissued_quote_cannot_claim_an_issuance_timestamp(self):
        now = timezone.now()
        for state in ("draft", "approved"):
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self.offer(status=state, reviewed_at=now,
                           issued_at=now).full_clean()

    def test_unaccepted_quote_cannot_hold_customer_acceptance_evidence(self):
        now = timezone.now()
        for state in ("draft", "approved", "issued"):
            params = dict(
                status=state, reviewed_at=now - timedelta(minutes=20),
                acceptance_reference="signed-by-customer",
                accepted_at=now - timedelta(minutes=1),
            )
            if state == "issued":
                params.update(issued_at=now - timedelta(minutes=10),
                              expires_at=now + timedelta(days=7))
            with self.subTest(state=state), self.assertRaises(ValidationError):
                self.offer(**params).full_clean()

