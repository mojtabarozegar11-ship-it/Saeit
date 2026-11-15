"""Customer receives an actual written offer, not a phantom paid invoice.

No email, chain RPC or payment is performed. Signed URL is private by default.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from core.models import MojPropOffer, MojPropRequest
from core.mojprop_quote_views import quote_read_token


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "zomorodmelal.ir", "testserver"])
class CustomerQuoteTokenTests(TestCase):
    def setUp(self):
        self.client = Client()
        now = timezone.now()
        self.lead = MojPropRequest.objects.create(
            request_id="MOJPROP-20261115-ABCD4455",
            name="PRIVATE BUYER NAME",
            email="private-buyer@example.org",
            route="blueprint", horizon="week",
            notes="An educational planning request with sensitive customer notes.",
            consent=True,
        )
        self.quote = MojPropOffer.objects.create(
            lead=self.lead, version=1,
            title="Economic production feasibility analysis",
            scope="A detailed economic feasibility analysis with sources, costs and risk scenarios.",
            amount=Decimal("125.00"), currency="USD", delivery_days=7,
            status="issued", reviewed_at=now-timedelta(hours=2),
            issued_at=now-timedelta(hours=1),
            expires_at=now+timedelta(days=3),
        )
        self.token = quote_read_token(self.quote)

    def view(self, token=None, host="mojplaywin.com", secure=True):
        return self.client.get(
            reverse("mojprop_quote_public", kwargs={
                "token": self.token if token is None else token,
            }),
            secure=secure, HTTP_HOST=host,
        )

    def test_public_view_is_default_off_even_with_valid_token(self):
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_issued_offer_is_readable_without_exposing_buyer_identity(self):
        response = self.view()
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("125.00 USD", content)
        self.assertIn("NOT A PAYMENT INVOICE", content)
        self.assertNotIn("private-buyer@example.org", content)
        self.assertNotIn("PRIVATE BUYER NAME", content)
        self.assertNotIn("sensitive customer notes", content)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("no-referrer", response["Referrer-Policy"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_only_https_and_approved_hostnames_can_open_quoted_terms(self):
        self.assertEqual(self.view(secure=False).status_code, 404)
        self.assertEqual(self.view(host="testserver").status_code, 404)
        self.assertEqual(self.view(host="zomorodmelal.ir").status_code, 200)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_tampered_token_and_mismatched_version_are_refused(self):
        self.assertEqual(self.view(token=self.token[:-1]+"x").status_code, 404)
        self.quote.version = 2
        self.quote.save(update_fields=["version"])
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_cancelled_and_expired_offers_are_not_publicly_readable(self):
        self.quote.status = "cancelled"
        self.quote.save(update_fields=["status"])
        self.assertEqual(self.view().status_code, 404)
        self.quote.status = "issued"
        self.quote.expires_at = timezone.now()-timedelta(seconds=1)
        self.quote.save(update_fields=["status", "expires_at"])
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_token_expires_independently_after_twenty_four_hours(self):
        import django.core.signing as signing
        moment = signing.time.time()
        with patch("django.core.signing.time.time", return_value=moment+86401):
            self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_new_issued_revision_invalidates_previous_customer_link(self):
        new = MojPropOffer.objects.create(
            lead=self.lead, version=2,
            title="Updated production economics service",
            scope="A re-scoped evidence-backed economics report with dated sources, scenario analyses and explicit limitations.",
            amount=Decimal("135.00"), currency="USD", delivery_days=10,
            status="issued", reviewed_at=timezone.now()-timedelta(hours=1),
            issued_at=timezone.now()-timedelta(minutes=30),
            expires_at=timezone.now()+timedelta(days=5),
        )
        self.assertEqual(self.view().status_code, 404)
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)
        self.assertIn("135.00 USD", self.view(
            token=quote_read_token(new),
        ).content.decode("utf-8"))

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_unreviewed_record_cannot_leak_quote_without_proof(self):
        self.quote.reviewed_at = None
        self.quote.save(update_fields=["reviewed_at"])
        self.assertEqual(self.view().status_code, 404)
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)

    def test_draft_offer_never_generates_shareable_buyer_token(self):
        self.quote.status = "draft"
        self.quote.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_accepted_quote_requires_independent_acceptance_proof(self):
        self.quote.status = "accepted"
        self.quote.accepted_at = timezone.now()
        self.quote.acceptance_reference = ""
        self.quote.save(update_fields=[
            "status", "accepted_at", "acceptance_reference",
        ])
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_accepted_quote_proof_must_follow_issuance_and_precede_expiry(self):
        self.quote.status = "accepted"
        self.quote.acceptance_reference = "buyer-consent:verified-2026"
        for when in (
            self.quote.issued_at - timedelta(seconds=1),
            self.quote.expires_at,
        ):
            with self.subTest(when=when.isoformat()):
                self.quote.accepted_at = when
                self.quote.save(update_fields=[
                    "status", "acceptance_reference", "accepted_at",
                ])
                with self.assertRaises(ValueError):
                    quote_read_token(self.quote)
                self.assertEqual(self.view().status_code, 404)


    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_future_issued_quote_cannot_be_read_by_customer(self):
        self.quote.issued_at = timezone.now() + timedelta(minutes=5)
        self.quote.reviewed_at = self.quote.issued_at - timedelta(minutes=10)
        self.quote.save(update_fields=["issued_at", "reviewed_at"])
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_future_accepted_quote_does_not_count_as_customer_signed(self):
        self.quote.status = "accepted"
        self.quote.accepted_at = timezone.now() + timedelta(minutes=2)
        self.quote.acceptance_reference = "buyer-consent:validated-document-001"
        self.quote.save(update_fields=[
            "status", "accepted_at", "acceptance_reference",
        ])
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_quote_from_past_issue_keeps_existing_read_access(self):
        self.assertEqual(self.view().status_code, 200)
        self.assertIn("NOT A PAYMENT INVOICE", self.view().content.decode("utf-8"))

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_future_review_timestamp_cannot_backdate_written_offer(self):
        self.quote.reviewed_at = timezone.now() + timedelta(hours=1)
        self.quote.issued_at = timezone.now() + timedelta(hours=2)
        self.quote.save(update_fields=["reviewed_at", "issued_at"])
        with self.assertRaises(ValueError):
            quote_read_token(self.quote)
        self.assertEqual(self.view().status_code, 404)

    @override_settings(MOJPROP_PUBLIC_QUOTES_ENABLED=True)
    def test_corrupt_contract_view_responds_404_without_exposing_internal_terms(self):
        from core.mojprop_quote_contract import QuoteContractError
        with patch("core.mojprop_quote_views.make_quote_snapshot",
                   side_effect=QuoteContractError("private quote integrity failure")):
            response = self.view()
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"private quote integrity failure", response.content)
        self.assertNotIn(b"private-buyer@example.org", response.content)
