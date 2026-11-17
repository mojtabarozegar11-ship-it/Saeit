"""Standalone current-main regression for the actual TRX guest checkout route.

The checkout URL may match the legacy private namespace while Django resolves
it to a different, prepended public handler. All checks are source/runtime-only:
no order, wallet access, invoice, email or payment is created.
"""
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.urls import NoReverseMatch, Resolver404

from core.mojplaywin_checkout_route import verified_guest_checkout_url


class EffectiveGuestCheckoutRouteTests(unittest.TestCase):
    def setUp(self):
        self.guest_view = lambda request, product_id: None
        package = ModuleType("services")
        package.__path__ = []
        pages = ModuleType("services.mpw_trx_public_pages")
        pages.product_checkout = self.guest_view
        self.module_patch = patch.dict(sys.modules, {
            "services": package,
            "services.mpw_trx_public_pages": pages,
        })
        self.module_patch.start()

    def tearDown(self):
        self.module_patch.stop()

    def match(self, *, name="mpw_trx_public_product", view=None, namespaces=()):
        return SimpleNamespace(
            url_name=name, namespaces=namespaces,
            func=self.guest_view if view is None else view,
        )

    def test_exact_effective_guest_handler_returns_checkout_path(self):
        with patch("django.urls.reverse", return_value="/commerce/book/72/") as reverse, patch(
            "django.urls.resolve", return_value=self.match(),
        ) as resolve:
            self.assertEqual(verified_guest_checkout_url(72), "/commerce/book/72/")
        reverse.assert_called_once_with(
            "mpw_trx_public_product", kwargs={"product_id": 72}
        )
        resolve.assert_called_once_with("/commerce/book/72/")

    def test_legacy_book_name_is_not_accepted(self):
        with patch("django.urls.reverse", return_value="/commerce/book/72/"), patch(
            "django.urls.resolve",
            return_value=self.match(name="book", namespaces=("mpw_commerce",)),
        ):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_same_path_but_different_callback_is_not_accepted(self):
        with patch("django.urls.reverse", return_value="/commerce/book/72/"), patch(
            "django.urls.resolve",
            return_value=self.match(view=lambda request, product_id: None),
        ):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_foreign_namespace_is_rejected(self):
        with patch("django.urls.reverse", return_value="/commerce/book/72/"), patch(
            "django.urls.resolve", return_value=self.match(namespaces=("foreign",)),
        ):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_untrusted_path_and_wrong_product_are_rejected(self):
        for value in (
            "https://evil.example/commerce/book/72/",
            "//evil.example/commerce/book/72/",
            "/commerce/book/73/",
            "/commerce/book/72/?next=evil",
            "/other/checkout/",
        ):
            with self.subTest(path=value), patch(
                "django.urls.reverse", return_value=value
            ):
                self.assertIsNone(verified_guest_checkout_url(72))

    def test_missing_route_rejected(self):
        with patch("django.urls.reverse", side_effect=NoReverseMatch("missing")):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_reverse_only_is_insufficient_without_resolving(self):
        with patch("django.urls.reverse", return_value="/commerce/book/72/"), patch(
            "django.urls.resolve", side_effect=Resolver404({"path": "missing"}),
        ):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_invalid_product_identifiers_are_rejected_before_reverse(self):
        for product_id in (None, True, False, 0, -1, "72", 72.0):
            with self.subTest(product_id=product_id), patch("django.urls.reverse") as reverse:
                self.assertIsNone(verified_guest_checkout_url(product_id))
                reverse.assert_not_called()

    def test_missing_private_gateway_is_not_a_payment_link(self):
        with patch.dict(sys.modules, {"services.mpw_trx_public_pages": None}):
            self.assertIsNone(verified_guest_checkout_url(72))

    def test_stale_imported_callback_is_rejected(self):
        sys.modules["services.mpw_trx_public_pages"].product_checkout = (
            lambda request, product_id: None
        )
        with patch("django.urls.reverse", return_value="/commerce/book/72/"), patch(
            "django.urls.resolve", return_value=self.match(),
        ):
            self.assertIsNone(verified_guest_checkout_url(72))


if __name__ == "__main__":
    unittest.main()
