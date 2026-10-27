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


    def test_invoice_recovery_link_contrast_and_keyboard_focus(self):
        self.assertIn(".mpw-shop-payment a{color:#f0d98f!important;text-decoration:underline", self.page)
        self.assertIn(".mpw-shop-payment a:focus-visible{outline:3px solid #fff", self.page)
        self.assertIn("background:#111310", self.page)

        def luminance(color):
            values = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
            return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        foreground, background = luminance("#f0d98f"), luminance("#111310")
        contrast = (max(foreground, background) + 0.05) / (min(foreground, background) + 0.05)
        self.assertGreaterEqual(contrast, 4.5)


if __name__ == "__main__":
    unittest.main()
