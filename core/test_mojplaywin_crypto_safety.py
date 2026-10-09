"""Fail-closed regression tests for MojPlayWin crypto payment records.

These tests do not enable a payment gateway or submit transactions.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import CryptoPaymentIntent, Order


class CryptoPaymentSafetyTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.customer = User.objects.create_user(username="crypto_safety_customer", password="test-only-password")
        self.order = Order.objects.create(customer=self.customer, total=Decimal("10.00"), currency="USD")

    def intent(self, **overrides):
        fields = dict(
            order=self.order, network="TRON", asset="TRX",
            amount=Decimal("5.000000000000000000"),
            quote_currency="USD", quote_amount=Decimal("10.00"),
            receiving_address="TTestOnlyNotARealPaymentAddress",
            required_confirmations=20,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        fields.update(overrides)
        return CryptoPaymentIntent(**fields)

    def test_missing_recipient_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.intent(receiving_address="").full_clean()

    def test_confirmed_requires_transaction_hash(self):
        with self.assertRaises(ValidationError):
            self.intent(status=CryptoPaymentIntent.CONFIRMED,
                        confirmations=20, verified_at=timezone.now()).full_clean()

    def test_confirmed_requires_sufficient_confirmations(self):
        with self.assertRaises(ValidationError):
            self.intent(status=CryptoPaymentIntent.CONFIRMED,
                        tx_hash="test-hash", confirmations=19,
                        verified_at=timezone.now()).full_clean()

    def test_confirmed_requires_verification_timestamp(self):
        with self.assertRaises(ValidationError):
            self.intent(status=CryptoPaymentIntent.CONFIRMED,
                        tx_hash="test-hash", confirmations=20).full_clean()

    def test_awaiting_payment_is_not_settled(self):
        intent = self.intent()
        intent.full_clean()
        self.assertEqual(intent.status, CryptoPaymentIntent.AWAITING_PAYMENT)
        self.assertIsNone(intent.verified_at)

    def test_default_crypto_checkout_is_disabled(self):
        from django.conf import settings
        self.assertFalse(settings.MOJPLAYWIN_CRYPTO_CHECKOUT_ENABLED)

    def test_crypto_record_cannot_be_created_without_an_order(self):
        with self.assertRaises(ValidationError):
            self.intent(order=None).full_clean()

    def test_crypto_record_is_unique_per_order(self):
        first = self.intent()
        first.full_clean()
        first.save()
        with self.assertRaises(ValidationError):
            self.intent(asset="ETH", network="ETHEREUM").full_clean()
