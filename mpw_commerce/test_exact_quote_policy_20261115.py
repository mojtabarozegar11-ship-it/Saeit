"""No live payment: regression tests for exact-amount multi-invoice quoting."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Order
from mpw_commerce.invoicing import (
    RECEIVERS, TrustedRate, VerifiedBuyer, reserve_order_invoice,
)
from mpw_commerce.models import CommerceInvoice


@override_settings(MPW_COMMERCE_INVOICING_ENABLED=True)
class ExactQuotePolicyTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="exact-quote-buyer", email="exact-quote-buyer@example.test"
        )
        self.orders = [
            Order.objects.create(
                customer=user, status="pending",
                total=Decimal("29.00"), currency="USD",
            )
            for _ in range(2)
        ]
        self.now = timezone.now()

    def _issue(self, order, asset, sender, price):
        buyer = VerifiedBuyer(
            sender=sender,
            challenge_id=f"verified-wallet-order-{order.pk}",
            verified_at=self.now,
        )
        quote = TrustedRate(
            usd_per_asset=Decimal(price),
            source="coinbase",
            observed_at=self.now,
        )
        with patch(
            "mpw_commerce.invoicing.order_snapshot",
            return_value=(Decimal("29.00"), []),
        ):
            return reserve_order_invoice(
                order.pk, asset, buyer=buyer, quote=quote, now=self.now
            )

    def test_equal_price_tron_orders_get_equal_explicit_exact_quote(self):
        sender = RECEIVERS["TRX"][1]
        a = self._issue(self.orders[0], "TRX", sender, "0.2")
        b = self._issue(self.orders[1], "TRX", sender, "0.2")
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(a.amount_atomic, "145000000")
        self.assertEqual(a.amount_atomic, b.amount_atomic)
        self.assertEqual(a.network, "tron-mainnet")
        self.assertEqual(b.network, "tron-mainnet")
        self.assertEqual(CommerceInvoice.objects.count(), 2)

    def test_equal_price_eth_orders_have_no_random_wallet_markup(self):
        sender = "0x" + "1" * 40
        a = self._issue(self.orders[0], "ETH", sender, "2900")
        b = self._issue(self.orders[1], "ETH", sender, "2900")
        self.assertEqual(a.amount_atomic, "10000000000000000")
        self.assertEqual(a.amount_atomic, b.amount_atomic)
        self.assertEqual(CommerceInvoice.objects.count(), 2)

    def test_one_order_still_cannot_reserve_two_invoices(self):
        from mpw_commerce.invoicing import InvoiceRejected
        sender = RECEIVERS["TRX"][1]
        self._issue(self.orders[0], "TRX", sender, "0.2")
        with self.assertRaises(InvoiceRejected):
            self._issue(self.orders[0], "TRX", sender, "0.2")
        self.assertEqual(CommerceInvoice.objects.count(), 1)

    def test_bad_server_clock_never_reaches_order_mutation(self):
        from datetime import datetime
        from mpw_commerce.invoicing import InvoiceRejected
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "valid-challenge-101", self.now)
        quote = TrustedRate(Decimal("0.2"), "coinbase", self.now)
        for invalid in (0, "2026-11-15T10:00:00Z", datetime(2026, 11, 15, 10, 0)):
            with self.subTest(clock=repr(invalid)), self.assertRaises(InvoiceRejected):
                reserve_order_invoice(self.orders[0].pk, "TRX", buyer=buyer,
                                      quote=quote, now=invalid)
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_invalid_wallet_challenge_and_timestamp_cannot_lock_invoice(self):
        from datetime import datetime
        from mpw_commerce.invoicing import InvoiceRejected
        valid_quote = TrustedRate(Decimal("0.2"), "coinbase", self.now)
        for challenge in ("hello world", "bad\nchallenge", "bad" + chr(0xD800),
                          "x" * 129, None, [], "short"):
            with self.subTest(challenge=repr(challenge)), self.assertRaises(InvoiceRejected):
                buyer = VerifiedBuyer(RECEIVERS["TRX"][1], challenge, self.now)
                reserve_order_invoice(self.orders[0].pk, "TRX", buyer=buyer,
                                      quote=valid_quote, now=self.now)
        for invalid_time in (None, 42, "2026-11-15T10:00:00Z",
                             datetime(2026, 11, 15, 10, 0)):
            with self.subTest(time=repr(invalid_time)), self.assertRaises(InvoiceRejected):
                buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "valid-challenge-101", invalid_time)
                reserve_order_invoice(self.orders[0].pk, "TRX", buyer=buyer,
                                      quote=valid_quote, now=self.now)
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_invalid_rate_observation_time_rejected_without_server_error(self):
        from datetime import datetime
        from mpw_commerce.invoicing import InvoiceRejected
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "valid-challenge-101", self.now)
        for invalid in (None, False, "2026-11-15T10:00:00Z",
                        datetime(2026, 11, 15, 10, 0)):
            with self.subTest(time=repr(invalid)), self.assertRaises(InvoiceRejected):
                quote = TrustedRate(Decimal("0.2"), "coinbase", invalid)
                reserve_order_invoice(self.orders[0].pk, "TRX", buyer=buyer,
                                      quote=quote, now=self.now)
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_trusted_rate_requires_exact_decimal_not_float_coercion(self):
        from mpw_commerce.invoicing import InvoiceRejected
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "valid-challenge-101", self.now)
        for wrong in (0.2, "0.2", 2, None, True, [], {}):
            with self.subTest(rate=repr(wrong)), self.assertRaises(InvoiceRejected):
                reserve_order_invoice(
                    self.orders[0].pk, "TRX", buyer=buyer,
                    quote=TrustedRate(wrong, "coinbase", self.now),
                    now=self.now,
                )
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_unknown_order_returns_domain_error_without_creating_invoice(self):
        from mpw_commerce.invoicing import InvoiceRejected
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "valid-challenge-101", self.now)
        quote = TrustedRate(Decimal("0.2"), "coinbase", self.now)
        with self.assertRaisesRegex(InvoiceRejected, "Unknown order"):
            reserve_order_invoice(
                9999999, "TRX", buyer=buyer, quote=quote, now=self.now,
            )
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_rate_that_cannot_fit_decimal_30_12_is_not_a_payment_quote(self):
        from mpw_commerce.invoicing import InvoiceRejected
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "verified-wallet-quote-22", self.now)
        bad_rates = (
            Decimal("0.0000000000001"),
            Decimal("0.1234567890123"),
            Decimal("999999999999999999.9999999999991"),
            Decimal("1000000000000000000"),
            Decimal("1E-80"),
        )
        for bad in bad_rates:
            with self.subTest(rate=str(bad)), self.assertRaises(InvoiceRejected):
                reserve_order_invoice(
                    self.orders[0].pk, "TRX", buyer=buyer,
                    quote=TrustedRate(bad, "coinbase", self.now),
                    now=self.now,
                )
        self.assertEqual(CommerceInvoice.objects.count(), 0)

    def test_source_comparison_object_cannot_impersonate_trusted_exchange(self):
        from mpw_commerce.invoicing import InvoiceRejected
        class Impersonator:
            def __eq__(self, other):
                return other == "coinbase"
        buyer = VerifiedBuyer(RECEIVERS["TRX"][1], "verified-wallet-quote-22", self.now)
        with self.assertRaises(InvoiceRejected):
            reserve_order_invoice(
                self.orders[0].pk, "TRX", buyer=buyer,
                quote=TrustedRate(Decimal("0.2"), Impersonator(), self.now),
                now=self.now,
            )
        self.assertEqual(CommerceInvoice.objects.count(), 0)
