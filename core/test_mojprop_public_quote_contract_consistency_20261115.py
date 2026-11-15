"""Django public proposal must obey the same source contract as manual quote snapshots.

This suite uses only an isolated test database and local GET; no mail, live
request, real purchase, financial transaction, payment or production writes.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import MojPropOffer, MojPropRequest
from core.mojprop_quote_views import quote_read_token


@override_settings(
    ALLOWED_HOSTS=["mojplaywin.com", "testserver"],
    MOJPROP_PUBLIC_QUOTES_ENABLED=True,
)
class PublicQuoteContractConsistencyTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-QUOTEVIEW",
            name="Example private client",
            email="example@invalid.test",
            route="blueprint",
            horizon="week",
            notes="Private, source-backed economic research for a potential client.",
            consent=True,
        )
        self.offer = MojPropOffer.objects.create(
            lead=self.lead, version=1, status="issued",
            title="Independent financial planning analysis",
            scope="A precise independent agricultural production budget and "
                  "feasibility assessment with scenarios and stated limitations.",
            exclusions="No real trading, settlement, or payment authorization.",
            amount=Decimal("125.00"), currency="USD", delivery_days=7,
            reviewed_at=now - timedelta(hours=2),
            issued_at=now - timedelta(hours=1),
            expires_at=now + timedelta(days=5),
        )
        self.token = quote_read_token(self.offer)
        self.client = Client()

    def url(self):
        return reverse("mojprop_quote_public", kwargs={"token": self.token})

    def view(self):
        return self.client.get(self.url(), secure=True, HTTP_HOST="mojplaywin.com")

    def mutate(self, **changes):
        MojPropOffer.objects.filter(pk=self.offer.pk).update(**changes)
        self.offer.refresh_from_db()

    def test_01_valid_issued_quote_readable_not_invoice(self):
        response = self.view()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NOT A PAYMENT INVOICE", response.content)
        self.assertIn(b"No payment has been collected", response.content)

    def test_02_valid_accepted_quote_readable_not_paid(self):
        self.mutate(
            status="accepted",
            accepted_at=timezone.now() - timedelta(minutes=3),
            acceptance_reference="buyer-approved:reference-2026",
        )
        response = self.view()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No payment has been collected", response.content)

    def test_03_short_acceptance_reference_never_published(self):
        self.mutate(
            status="accepted", accepted_at=timezone.now(),
            acceptance_reference="yes",
        )
        self.assertEqual(self.view().status_code, 404)

    def test_04_direction_override_reference_never_published(self):
        self.mutate(
            status="accepted", accepted_at=timezone.now(),
            acceptance_reference="buyer-" + chr(0x202E) + "-approval",
        )
        self.assertEqual(self.view().status_code, 404)

    def test_05_future_accepted_time_never_published(self):
        self.mutate(
            status="accepted", accepted_at=timezone.now() + timedelta(minutes=2),
            acceptance_reference="buyer-approved:future-reference",
        )
        self.assertEqual(self.view().status_code, 404)

    def test_06_unapproved_currency_never_published(self):
        self.mutate(currency="BTC")
        self.assertEqual(self.view().status_code, 404)

    def test_07_underdefined_service_scope_never_published(self):
        self.mutate(scope="Brief")
        self.assertEqual(self.view().status_code, 404)

    def test_08_unexplained_exclusions_never_published(self):
        self.mutate(exclusions="None")
        self.assertEqual(self.view().status_code, 404)

    def test_09_quote_exceeding_ninety_day_window_never_published(self):
        self.mutate(expires_at=self.offer.issued_at + timedelta(days=91))
        self.assertEqual(self.view().status_code, 404)

    def test_10_issued_status_with_earlier_acceptance_evidence_never_published(self):
        self.mutate(accepted_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.view().status_code, 404)

    def test_11_issued_status_with_unreviewed_reference_never_published(self):
        self.mutate(acceptance_reference="buyer-accepted-without-status")
        self.assertEqual(self.view().status_code, 404)

    def test_12_quote_signing_fails_for_unapproved_currency(self):
        self.mutate(currency="BTC")
        with self.assertRaises(ValueError):
            quote_read_token(self.offer)

    def test_13_quote_signing_fails_for_future_acceptance(self):
        self.mutate(
            status="accepted", accepted_at=timezone.now() + timedelta(minutes=3),
            acceptance_reference="buyer-approval:premature",
        )
        with self.assertRaises(ValueError):
            quote_read_token(self.offer)

    def test_14_no_private_email_in_public_valid_quote(self):
        response = self.view()
        self.assertNotIn(b"example@invalid.test", response.content)
        self.assertNotIn(b"Example private client", response.content)

    def test_15_response_cannot_be_cached_by_shared_proxy(self):
        response = self.view()
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")

    def test_16_unauthorised_host_denied_even_with_signed_quote(self):
        response = self.client.get(self.url(), secure=True, HTTP_HOST="testserver")
        self.assertEqual(response.status_code, 404)

    def test_17_insecure_link_denied_even_with_signed_quote(self):
        response = self.client.get(self.url(), secure=False, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 404)

    def test_18_cancelled_offer_cannot_be_replayed(self):
        self.mutate(status="cancelled")
        self.assertEqual(self.view().status_code, 404)

    def test_19_expired_offer_cannot_be_replayed(self):
        self.mutate(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.view().status_code, 404)

    def test_20_same_issued_quote_cannot_claim_delivery(self):
        response = self.view()
        self.assertNotIn(b"Payment received", response.content)
        self.assertNotIn(b"File delivered", response.content)


