"""Regression coverage for the private-approved MojPlayWin SKU catalogue.

No payment, blockchain, email, customer order or real access tokens used.
"""
from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.mojplaywin_dynamic_catalog import (
    ApprovedCard, _linked_product, _verified_private_gateway,
    approved_cards, approved_product, parse_cursor,
)
from django.urls import NoReverseMatch


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "evil.example",
])
class ApprovedCatalogueTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.product = SimpleNamespace(
            pk=901, title="Original licensed digital field guide",
            currency="USD", price="14.00",
        )

    def request(self, host="mojplaywin.com", secure=True, path="/store/"):
        return self.factory.get(path, secure=secure, HTTP_HOST=host)

    def approved_route(self):
        return (
            patch("core.mojplaywin_dynamic_catalog.reverse",
                  return_value="/commerce/book/901/"),
            patch("core.mojplaywin_dynamic_catalog.resolve",
                  return_value=SimpleNamespace(
                      url_name="book", namespaces=["mpw_commerce"])),
        )

    def test_cursor_validates_ascii_only(self):
        self.assertEqual(parse_cursor("0"), 0)
        self.assertEqual(parse_cursor("901"), 901)
        for item in ("", " 1", "+1", "-1", "١", "１２", "3.1", "1e4",
                     "99999999999999999", 3, None):
            with self.subTest(item=item), self.assertRaises(Http404):
                parse_cursor(item)

    def test_plain_http_cannot_see_private_catalogue(self):
        self.assertIsNone(_verified_private_gateway(self.request(secure=False)))

    def test_foreign_host_cannot_see_private_catalogue(self):
        self.assertIsNone(_verified_private_gateway(self.request("evil.example")))
        self.assertIsNone(_verified_private_gateway(self.request("zomorodmelal.ir")))

    def test_missing_private_gateway_does_not_expose_payable_stock(self):
        self.assertIsNone(_verified_private_gateway(self.request()))

    def test_valid_licenced_item_renders_exact_detail_path(self):
        reverse_patch, resolve_patch = self.approved_route()
        with reverse_patch, resolve_patch:
            card = _linked_product(self.product)
        self.assertEqual(card.product_id, 901)
        self.assertEqual(card.price_usd, "14.00")
        self.assertEqual(card.detail_url, "/store/product/901/")

    def test_wrong_checkout_namespace_is_refused(self):
        with patch("core.mojplaywin_dynamic_catalog.reverse",
                   return_value="/commerce/book/901/"), patch(
            "core.mojplaywin_dynamic_catalog.resolve",
            return_value=SimpleNamespace(url_name="book", namespaces=[]),
        ):
            self.assertIsNone(_linked_product(self.product))

    def test_missing_checkout_route_is_refused(self):
        with patch("core.mojplaywin_dynamic_catalog.reverse",
                   side_effect=NoReverseMatch("not installed")):
            self.assertIsNone(_linked_product(self.product))

    def test_price_and_currency_validation_rejects_unapproved_quote(self):
        invalid = ("0", "-1", "1001", "1.001", "NaN", "Infinity")
        for amount in invalid:
            with self.subTest(amount=amount):
                candidate = SimpleNamespace(
                    pk=901, title="Product", currency="USD", price=amount)
                self.assertIsNone(_linked_product(candidate))
        candidate = SimpleNamespace(
            pk=901, title="Product", currency="EUR", price="14")
        self.assertIsNone(_linked_product(candidate))

    def test_bad_product_identity_is_refused(self):
        for pk in ("901", True, -1, 0, 1.5):
            with self.subTest(pk=pk):
                candidate = SimpleNamespace(
                    pk=pk, title="Product", currency="USD", price="14")
                self.assertIsNone(_linked_product(candidate))

    def test_approved_listing_rechecks_each_sku(self):
        reverse_patch, resolve_patch = self.approved_route()
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([self.product], False),
                                 lambda pk: self.product)), reverse_patch, resolve_patch:
            rows, next_cursor = approved_cards(self.request())
        self.assertEqual([row.product_id for row in rows], [901])
        self.assertIsNone(next_cursor)

    def test_stale_item_cannot_appear_even_if_list_was_approved(self):
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([self.product], False),
                                 lambda pk: None)):
            rows, next_cursor = approved_cards(self.request())
        self.assertEqual(rows, ())
        self.assertIsNone(next_cursor)

    def test_duplicate_or_unsorted_ids_abort_whole_page(self):
        other = SimpleNamespace(
            pk=800, title="Old stock", currency="USD", price="6")
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([self.product, other], False),
                                 lambda pk: self.product)):
            rows, cursor = approved_cards(self.request())
        self.assertEqual((rows, cursor), ((), None))

    def test_more_than_one_page_of_gateway_stock_is_refused(self):
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([self.product] * 25, True),
                                 lambda pk: self.product)):
            rows, cursor = approved_cards(self.request())
        self.assertEqual((rows, cursor), ((), None))

    def test_curated_ids_are_not_duplicated_in_new_arrivals(self):
        original = SimpleNamespace(
            pk=72, title="Original chess", currency="USD", price="7.50")
        reverse_patch, resolve_patch = self.approved_route()
        # Route mismatch for 72 is itself an independent reason not to list.
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([original], True),
                                 lambda pk: original)), reverse_patch, resolve_patch:
            rows, next_cursor = approved_cards(
                self.request(), excluded_ids=frozenset({72}))
        self.assertEqual(rows, ())
        self.assertEqual(next_cursor, 72)

    def test_private_gateway_exception_does_not_take_store_down(self):
        def broken(after_id):
            raise RuntimeError("private component unavailable")
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(broken, lambda pk: self.product)):
            rows, cursor = approved_cards(self.request())
        self.assertEqual((rows, cursor), ((), None))

    def test_unapproved_product_lookup_fails_closed(self):
        with patch("core.mojplaywin_dynamic_catalog._verified_private_gateway",
                   return_value=(lambda after_id: ([], False), lambda pk: None)):
            self.assertIsNone(approved_product(self.request(), 901))


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
class DynamicStoreIntegrationTests(TestCase):
    def test_noncurated_sku_unavailable_without_private_gateway(self):
        response = self.client.get(
            "/store/product/901/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 404)

    def test_noncurated_approved_sku_gets_existing_licensed_detail_page(self):
        from core.models import Product
        p = Product.objects.create(pk=901, title="Verified downloadable journal",
                                   product_type="digital", currency="USD",
                                   price=Decimal("14.00"), active=True)
        with patch("core.mojplaywin_dynamic_catalog.approved_product",
                   return_value=p), patch(
            "core.mojplaywin_product_detail._approved_purchase_url",
            return_value="/commerce/book/901/",
        ):
            response = self.client.get(
                "/store/product/901/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verified downloadable journal")
        self.assertContains(response, 'href="/commerce/book/901/"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_new_approved_stock_is_visible_on_store_without_raw_checkout_link(self):
        item = ApprovedCard(
            901, "Original journal", "14.00", "/store/product/901/")
        with patch("core.mojplaywin_dynamic_catalog.approved_cards",
                   return_value=((item,), None)):
            response = self.client.get(
                "/store/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original journal")
        self.assertContains(response, 'href="/store/product/901/"')
        self.assertNotContains(response, 'href="/commerce/book/901/"')
        self.assertIn("no-store", response["Cache-Control"])

    def test_malformed_cursor_is_rejected_before_catalogue_lookup(self):
        response = self.client.get(
            "/store/?approved_after=bad", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 404)

    def test_pagination_points_only_to_store_not_invoice(self):
        with patch("core.mojplaywin_dynamic_catalog.approved_cards",
                   return_value=((), 901)):
            response = self.client.get(
                "/store/", secure=True, HTTP_HOST="mojplaywin.com")
        self.assertContains(response, "/store/?approved_after=901")
        self.assertNotContains(response, "/commerce/book/901/")
