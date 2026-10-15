"""Customer checkout UI and private receipt status — disposable Django only.

No production wallets, blockchain requests, sales, or paid-state writes.
"""
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import KnowledgeArticle, Order, OrderItem, Product
from mpw_commerce.models import CommerceInvoice


FLAGS = {
    "MPW_COMMERCE_RELEASE_READY": True,
    "MPW_COMMERCE_INVOICING_ENABLED": True,
    "MPW_COMMERCE_CUSTOMER_HTTP_ENABLED": True,
    "MPW_COMMERCE_BUYER_SIGNATURE_ENABLED": True,
    "MPW_COMMERCE_SETTLEMENT_ENABLED": True,
    "MPW_COMMERCE_REAL_RPC_ENABLED": True,
    "MPW_COMMERCE_AUTORECONCILE_ENABLED": True,
    "MPW_COMMERCE_DOWNLOADS_ENABLED": True,
}


class CustomerCheckoutPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username="book-checkout-buyer")
        self.seller = User.objects.create_user(username="book-checkout-owner")
        self.article = KnowledgeArticle.objects.create(
            title="Original chess book research",
            slug="chess-book-checkout-test",
            content="Test fixture only",
            published=True,
        )
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        Path(self.temp.name, "private.pdf").write_bytes(b"%PDF-1.4\nprivate test fixture\n")
        self.product = Product.objects.create(
            title="The Science and Practice of Chess Improvement",
            product_type="digital_book", price=Decimal("7.50"),
            currency="USD", active=True, owner=self.seller,
            knowledge_article=self.article,
            metadata={
                "factory_publication_permission": True,
                "asset_verified": True, "quality_approved": True,
                "license_verified": True,
                "mpw_commerce": {
                    "enabled": True, "fulfillment": "digital",
                    "private_file": "private.pdf",
                },
            },
        )
        self.client = Client()
        self.client.force_login(self.buyer)
        self.url = reverse("mpw_commerce:book", kwargs={"product_id": self.product.pk})
        settings = override_settings(**FLAGS, MPW_COMMERCE_PRIVATE_ASSET_ROOT=self.temp.name)
        settings.enable()
        self.addCleanup(settings.disable)
        proofs = patch(
            "mpw_commerce.product_checkout_page.proven_assets",
            return_value={"ETH": True, "TRX": True},
        )
        proofs.start()
        self.addCleanup(proofs.stop)

    def get(self, *, host="mojplaywin.com", secure=True):
        return self.client.get(self.url, secure=secure, HTTP_HOST=host)

    def test_approved_purchaser_sees_connected_checkout_without_wallet_details(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect wallet and request an invoice")
        self.assertContains(response, "$")
        self.assertContains(response, "7.50")
        self.assertContains(response, "/commerce/checkout/order/")
        self.assertContains(response, "/commerce/checkout/challenge/")
        self.assertContains(response, "/commerce/checkout/invoice/")
        self.assertContains(response, "/commerce/checkout/status/")
        self.assertContains(response, "Payment has not yet been independently confirmed")
        self.assertNotContains(response, "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73")
        self.assertNotContains(response, "0x89149b01f59115B86553561F12438D2ADF517E75")
        self.assertEqual(Order.objects.count(), 0)

    def test_signed_in_buyer_required_and_invalid_domain_denied(self):
        self.assertEqual(self.get(host="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.get(secure=False).status_code, 404)
        self.client.logout()
        self.assertEqual(self.get().status_code, 302)

    def test_each_release_switch_off_denies_buy_page(self):
        for flag in FLAGS:
            with self.subTest(flag=flag), override_settings(**{flag: False}):
                self.assertEqual(self.get().status_code, 404)
        self.assertEqual(Order.objects.count(), 0)

    def test_owner_proof_product_rights_article_and_file_are_all_required(self):
        with patch("mpw_commerce.product_checkout_page.proven_assets",
                   return_value={"ETH": True, "TRX": False}):
            self.assertEqual(self.get().status_code, 404)
        self.product.metadata["quality_approved"] = False
        self.product.save(update_fields=["metadata"])
        self.assertEqual(self.get().status_code, 404)
        self.product.metadata["quality_approved"] = True
        self.product.save(update_fields=["metadata"])
        self.article.published = False
        self.article.save(update_fields=["published"])
        self.assertEqual(self.get().status_code, 404)
        self.article.published = True
        self.article.save(update_fields=["published"])
        Path(self.temp.name, "private.pdf").unlink()
        self.assertEqual(self.get().status_code, 404)

    def test_invoice_status_exposes_no_download_unless_purchased_entitlement_proven(self):
        self.order = Order.objects.create(
            customer=self.buyer, total=Decimal("7.50"), currency="USD",
            status="paid",
        )
        invoice = SimpleNamespace(
            status=CommerceInvoice.Status.PAID,
            order=self.order, network="ethereum-mainnet", asset="ETH",
        )
        with patch("mpw_commerce.checkout_views.CommerceInvoice.objects.select_related") as qs:
            qs.return_value.filter.return_value.first.return_value = invoice
            with patch("mpw_commerce.entitlements.can_access_purchased_digital_item",
                       return_value=False):
                response = self.client.get(
                    reverse("mpw_commerce:status", kwargs={"order_id": self.order.pk}),
                    secure=True, HTTP_HOST="mojplaywin.com",
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["can_access_purchased_items"])
                self.assertEqual(response.json()["download_paths"], [])
        self.assertEqual(Order.objects.count(), 1)

    def test_proven_paid_buyer_receives_only_authenticated_download_path(self):
        order = Order.objects.create(
            customer=self.buyer, total=Decimal("7.50"), currency="USD",
            status="paid",
        )
        item = OrderItem.objects.create(
            order=order, product=self.product, quantity=1,
            unit_price=self.product.price, currency="USD",
        )
        invoice = SimpleNamespace(
            status=CommerceInvoice.Status.PAID,
            order=order, network="tron-mainnet", asset="TRX",
        )
        with patch("mpw_commerce.checkout_views.CommerceInvoice.objects.select_related") as qs:
            qs.return_value.filter.return_value.first.return_value = invoice
            with patch("mpw_commerce.entitlements.can_access_purchased_digital_item",
                       return_value=True) as entitlement:
                response = self.client.get(
                    reverse("mpw_commerce:status", kwargs={"order_id": order.pk}),
                    secure=True, HTTP_HOST="mojplaywin.com",
                )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["can_access_purchased_items"])
        self.assertEqual(response.json()["download_paths"], [
            reverse("mpw_commerce:download",kwargs={"item_id":item.pk})
        ])
        entitlement.assert_called_once_with(item.pk,self.buyer.pk)
