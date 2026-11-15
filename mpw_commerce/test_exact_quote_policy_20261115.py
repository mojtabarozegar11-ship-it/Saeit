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
