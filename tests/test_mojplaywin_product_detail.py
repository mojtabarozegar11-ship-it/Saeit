"""MojPlayWin product detail recovery without enabling unverified commerce."""
from django.test import TestCase, override_settings
from django.db import DatabaseError
from unittest.mock import patch
from core.models import CommerceFunnelEvent
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

    def test_product_detail_records_a_view_not_a_sale(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", currency="USD", price="7.50",
        )
        response = self.get(72)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CommerceFunnelEvent.objects.filter(event_name="view_item").count(), 1)
        self.assertEqual(CommerceFunnelEvent.objects.filter(event_name="payment_confirmed").count(), 0)

    def test_missing_optional_analytics_does_not_break_product_detail(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", currency="USD", price="7.50",
        )
        with patch("core.commerce_funnel.record_funnel_event", side_effect=RuntimeError("analytics off")):
            response = self.get(72)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PUBLIC_CATALOG[72]["title"])

    def test_catalog_database_error_degrades_to_safe_preview(self):
        with patch("core.mojplaywin_product_detail.Product.objects.filter",
                   side_effect=DatabaseError("unavailable optional product table")):
            response = self.get(72)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertContains(response, "Catalog preview")
        self.assertNotContains(response, "Buy now")

    def test_unmatched_product_does_not_create_funnel_view(self):
        response = self.get(72)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CommerceFunnelEvent.objects.exists())

    def test_three_product_catalog_does_not_claim_live_buy_in_text(self):
        response = self.client.get("/store/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Buy securely with TRX")
        self.assertNotContains(response, "View details &amp; purchase")
        self.assertContains(response, "Never send funds to an address found outside your verified order invoice.")

    def test_strict_catalog_id_count(self):
        self.assertEqual(set(PUBLIC_CATALOG), {72, 225, 879})

    def test_changed_price_must_be_preview_not_valid_catalog(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="book", currency="USD", price="9.99",
        )
        response = self.get(72)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_preview"])
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
        self.assertFalse(CommerceFunnelEvent.objects.exists())

    def test_currency_mismatch_does_not_inflate_availability(self):
        Product.objects.create(
            pk=225, title=PUBLIC_CATALOG[225]["title"], active=True,
            product_type="digital_book", currency="EUR", price="4.00",
        )
        response = self.get(225)
        self.assertTrue(response.context["is_preview"])
        self.assertFalse(CommerceFunnelEvent.objects.exists())

    def test_exact_declared_prices_all_have_one_source_of_truth(self):
        self.assertEqual(
            [PUBLIC_CATALOG[k]["expected_price_usd"] for k in (72,225,879)],
            ["7.50", "4.00", "6.80"],
        )

    def test_product_pages_are_never_shared_cached_across_customers(self):
        for product_id in (72, 225, 879):
            with self.subTest(product=product_id):
                response = self.get(product_id)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("private", response["Cache-Control"])
                self.assertIn("Cookie", response["Vary"])

    def test_gateway_purchase_link_is_never_cached_after_rights_revocation(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="digital_book", currency="USD", price="7.50",
        )
        with patch("core.mojplaywin_product_detail._approved_purchase_url",
                   return_value="/commerce/book/72/"):
            approved_response = self.get(72)
        self.assertTrue(approved_response.context["purchase_available"])
        self.assertIn("no-store", approved_response["Cache-Control"])
        with patch("core.mojplaywin_product_detail._approved_purchase_url",
                   return_value=None):
            held_response = self.get(72)
        self.assertFalse(held_response.context["purchase_available"])
        self.assertNotContains(held_response, 'href="/commerce/book/72/"')
        self.assertIn("no-store", held_response["Cache-Control"])

    def test_verified_private_gateway_can_restore_legitimate_buy_button(self):
        item = Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="digital_book", currency="USD", price="7.50",
        )
        with patch("core.mojplaywin_product_detail._approved_purchase_url",
                   return_value="/commerce/book/72/") as approved:
            response = self.get(72)
        approved.assert_called_once()
        self.assertTrue(response.context["purchase_available"])
        self.assertContains(response, 'href="/commerce/book/72/"')
        self.assertContains(response, "Continue to verified TRX checkout")
        self.assertContains(response, "Never send funds to an address found outside your verified order invoice.")

    def test_missing_private_gateway_holds_checkout_even_when_catalog_matches(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="digital_book", currency="USD", price="7.50",
        )
        response = self.get(72)
        self.assertFalse(response.context["purchase_available"])
        self.assertNotContains(response, 'href="/commerce/book/72/"')
        self.assertContains(response, "Purchasing on this page is not enabled.")

    def test_changed_db_price_fails_closed_until_catalog_is_corrected(self):
        Product.objects.create(
            pk=72, title=PUBLIC_CATALOG[72]["title"], active=True,
            product_type="digital_book", currency="USD", price="8.25",
        )
        with patch("core.mojplaywin_product_detail._approved_purchase_url",
                   return_value="/commerce/book/72/") as approved:
            response = self.get(72)
        self.assertIsNone(response.context["database_price_usd"])
        self.assertTrue(response.context["is_preview"])
        self.assertFalse(response.context["purchase_available"])
        approved.assert_not_called()
        self.assertNotContains(response, 'href="/commerce/book/72/"')
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_missing_product_does_not_consult_gateway(self):
        with patch("core.mojplaywin_product_detail._approved_purchase_url") as approved:
            response = self.get(72)
        self.assertFalse(response.context["purchase_available"])
        approved.assert_not_called()
