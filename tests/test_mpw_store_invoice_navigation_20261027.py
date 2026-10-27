"""Regression for public store invoice-recovery navigation (no payments)."""
from pathlib import Path
import unittest

TEMPLATE = Path(__file__).resolve().parents[1] / "core/templates/mojplaywin/store.html"


class StoreInvoiceNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = TEMPLATE.read_text(encoding="utf-8")

    def test_customer_has_single_purchases_and_invoices_link(self):
        self.assertEqual(self.page.count('href="/commerce/trx-easy/purchases/"'), 1)
        self.assertIn("View your purchases and invoices</a>", self.page)

    def test_existing_product_destinations_remain_intact(self):
        for sku in (72, 225, 879):
            with self.subTest(sku=sku):
                self.assertIn(f'href="/store/product/{sku}/"', self.page)

    def test_guidance_keeps_secure_invoice_warning(self):
        self.assertIn("Never send funds to an address found outside your verified order invoice.", self.page)
        self.assertNotIn('href="/invoices/"', self.page)


if __name__ == "__main__":
    unittest.main()
