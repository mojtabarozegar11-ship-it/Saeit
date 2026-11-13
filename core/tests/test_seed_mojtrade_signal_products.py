import os

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Product


@pytest.mark.django_db
class MojTradeSignalProductSeederTests(TestCase):
    def setUp(self):
        Product.objects.filter(product_type="signal").delete()

    def test_seed_is_idempotent_and_inactive_by_default(self):
        call_command("seed_mojtrade_signal_products")
        call_command("seed_mojtrade_signal_products")

        products = list(Product.objects.filter(product_type="signal").order_by("price"))
        self.assertEqual(len(products), 3)
        self.assertEqual([str(product.price) for product in products], ["5.00", "10.00", "15.00"])
        self.assertTrue(all(not product.active for product in products))
        self.assertTrue(all(product.currency == "TRX" for product in products))
        self.assertTrue(all(product.metadata["canonical_bot_id"] == "mojtaba.bot.ai" for product in products))
        self.assertTrue(all(product.metadata["validity_days"] == 15 for product in products))
        self.assertTrue(all(product.metadata["max_verified_signals"] == 10 for product in products))
        self.assertEqual(Product.objects.filter(product_type="signal").count(), 3)

    def test_activation_requires_explicit_release_flag(self):
        os.environ.pop("MOJ_SIGNAL_RELEASE_APPROVED", None)
        with self.assertRaises(CommandError) as raised:
            call_command("seed_mojtrade_signal_products", "--activate")
        self.assertEqual(str(raised.exception), "SIGNAL_RELEASE_APPROVAL_FLAG_REQUIRED")
        self.assertEqual(Product.objects.filter(product_type="signal").count(), 0)
