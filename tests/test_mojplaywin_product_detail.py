"""MojPlayWin product detail recovery without enabling unverified commerce."""
from django.test import TestCase, override_settings
from core.models import Product
from core.mojplaywin_product_detail import PUBLIC_CATALOG

HOSTS = ["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir",
         "evil.example", "localhost"]


@override_settings(ALLOWED_HOSTS=HOSTS)
class MojPlayWinProductDetailsTests(TestCase):
    def get(self, item_id, host="mojplaywin.com"):
        return self.client.get(f"/store/product/{item_id}/", HTTP_HOST=host)

    def test_three_curated_english_store_cards_have_detail_page(self):
        for item_id, item in PUBLIC_CATALOG.items():
            with self.subTest(product=item_id):
                response = self.get(item_id)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, item["title"])
                self.assertContains(response, item["listed_price"])

    def test_both_mojplaywin_hosts_supported(self):
        self.assertEqual(self.get(72, "www.mojplaywin.com").status_code, 200)

    def test_unknown_host_is_never_a_mojplaywin_offer(self):
        self.assertEqual(self.get(72, "evil.example").status_code, 404)
        self.assertEqual(self.get(72, "localhost").status_code, 404)

    def test_unknown_product_id_returns_404(self):
        self.assertEqual(self.get(999999).status_code, 404)

    def test_missing_db_record_is_honest_nonindexed_preview(self):
        response = self.get(72)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(response, "Product database availability is not confirmed")
        self.assertNotContains(response, "Pay now")

    def test_active_matching_database_product_is_not_buyable_without_checkout(self):
        Product.objects.create(
            pk=225, title=PUBLIC_CATALOG[225]["title"], active=True,
            product_type="digital_book", currency="USD", price="4.00",
        )
        response = self.get(225)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["purchase_available"])
        self.assertContains(response, "Mainnet payment and private delivery are not verified")
        self.assertNotContains(response, 'type="submit"')

    def test_reused_database_id_cannot_become_foreign_sale(self):
        Product.objects.create(
            pk=879, title="Another company's product", active=True,
            product_type="digital", currency="USD", price="6.80",
        )
        response = self.get(879)
        self.assertTrue(response.context["is_preview"])
        self.assertContains(response, "Atelier Interior")
        self.assertNotContains(response, "Another company")

    def test_zomorod_company_product_details_unchanged(self):
        Product.objects.create(pk=5671, title="Zomorod catalog",
                               active=True, product_type="book")
        response = self.get(5671, "zomorodmelal.ir")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zomorod catalog")

    def test_mojplaywin_does_not_expose_unrelated_company_product(self):
        Product.objects.create(pk=5671, title="Zomorod catalog",
                               active=True, product_type="book")
        self.assertEqual(self.get(5671).status_code, 404)

    def test_store_buy_buttons_do_not_point_to_unmounted_checkout(self):
        response = self.client.get("/store/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '/store/product/72/checkout/')
        self.assertNotContains(response, '/store/product/225/checkout/')
        self.assertContains(response, 'href="/store/product/72/"')
        self.assertContains(response, 'href="/store/product/225/"')

    def test_no_checkout_api_is_implied_on_details(self):
        response = self.get(72)
        html = response.content.decode("utf-8").lower()
        for unsafe in ('<form', 'sendtransaction(', '/commerce/trx-easy/start/',
                       'walletconnect', 'payment_confirmed'):
            self.assertNotIn(unsafe, html)

    def test_strict_catalog_id_count(self):
        self.assertEqual(set(PUBLIC_CATALOG), {72, 225, 879})
