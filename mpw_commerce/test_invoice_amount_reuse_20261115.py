from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from mpw_commerce.models import CommerceInvoice
from core.models import Order


class CommerceInvoiceAmountReuseTests(TestCase):
    def test_two_independent_orders_may_share_the_same_quote(self):
        user = get_user_model().objects.create_user(
            username="invoice-reuse-test",
            email="invoice-reuse@example.test",
        )
        now = timezone.now()
        orders = [
            Order.objects.create(
                customer=user, status="pending",
                total=Decimal("29.00"), currency="USD",
            )
            for _ in range(2)
        ]
        for order in orders:
            CommerceInvoice.objects.create(
                order=order,
                asset="TRX",
                network="tron-mainnet",
                recipient="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
                expected_sender="TA9pkx4DFxrEw8JZzUtyDrh2uAat1LDuJL",
                amount_atomic="1000000",
                total_usd=Decimal("29.00"),
                quote_usd_per_asset=Decimal("0.000029000000"),
                quote_source="test-fixture",
                quote_observed_at=now,
                sender_challenge_id=f"challenge-{order.pk}",
                sender_signature_verified_at=now,
                issued_at=now,
                expires_at=now + timedelta(minutes=30),
            )
        self.assertEqual(
            CommerceInvoice.objects.filter(
                network="tron-mainnet",
                recipient="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
                amount_atomic="1000000",
            ).count(),
            2,
        )
