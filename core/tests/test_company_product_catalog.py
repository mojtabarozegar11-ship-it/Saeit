from django.test import TestCase


class CompanyProductCatalogTests(TestCase):
    def test_company_product_catalog_is_complete_and_unique(self):
        response = self.client.get("/company/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("کاتالوگ کامل 55 زنجیره", html)
        self.assertIn("<strong>55</strong>", html)
        self.assertIn("<strong>41</strong>", html)
        self.assertEqual(html.count('class="company-product-chain"'), 55)
        self.assertEqual(html.count('class="company-product-top"'), 55)

    def test_company_product_catalog_has_high_value_taxonomy(self):
        response = self.client.get("/company/")
        html = response.content.decode("utf-8")
        for label in (
            "محصولات با ارزش افزوده بالا",
            "محصولات لوکس و صنایع دستی",
            "آبزی‌پروری ممتاز",
        ):
            self.assertIn(label, html)
