from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import GuestOrderEmail, LedgerEntry, Order, Product
from mpw_commerce.buyer_identity import BuyerIdentityConflict, record_buyer_identity
from mpw_commerce.models import CommerceBuyerIdentity


class BuyerIdentityProjectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="mpwguest_test_identity",
        )
        self.product = Product.objects.create(
            title="Identity fixture",
            product_type="digital",
            price="5.00",
            currency="USD",
            active=True,
        )
        self.order = Order.objects.create(
            customer=self.user,
            status="pending",
            total="5.00",
            currency="USD",
        )

    def test_checkout_claim_projects_email_without_using_guest_username(self):
        GuestOrderEmail.objects.create(
            order=self.order,
            email_address="buyer@example.com",
            email_digest="a" * 64,
        )
        identity = CommerceBuyerIdentity.objects.get(order=self.order)
        self.assertEqual(identity.email_address, "buyer@example.com")
        self.assertEqual(identity.email_digest, "a" * 64)
        self.assertEqual(identity.payer_wallet, "")

    def test_verified_credit_projects_sender_wallet(self):
        LedgerEntry.objects.create(
            order=self.order,
            entry_type="credit",
            amount="5.00",
            currency="USD",
            reference="walletless:tron-mainnet:" + "b" * 64,
            metadata={
                "payment_method": "mpw_walletless_trx_v1",
                "network": "tron-mainnet",
                "tx_hash": "b" * 64,
                "sender": "T" + "A" * 33,
            },
        )
        identity = CommerceBuyerIdentity.objects.get(order=self.order)
        self.assertEqual(identity.payer_wallet, "T" + "A" * 33)
        self.assertEqual(identity.network, "tron-mainnet")
        self.assertEqual(identity.tx_hash, "b" * 64)

    def test_existing_identity_cannot_be_reassigned(self):
        record_buyer_identity(order=self.order, email="buyer@example.com")
        with self.assertRaises(BuyerIdentityConflict):
            record_buyer_identity(order=self.order, email="other@example.com")
