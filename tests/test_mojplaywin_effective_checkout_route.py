"""Regression tests for the effective (not shadowed) native TRX guest route.

A duplicate legacy namespaced route can reverse to /commerce/book/<id>/
while a prepended public guest route is the only callback actually reached
by Django. No private gateway, wallet or customer transaction is invoked.
"""
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import NoReverseMatch, Resolver404

from core.mojplaywin_checkout_route import verified_guest_checkout_url
from core.mojplaywin_dynamic_catalog import _verified_private_gateway, approved_cards


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "evil.example"])
class EffectiveGuestRouteTests(SimpleTestCase):
    def setUp(self):
        self.guest_view = lambda request, product_id: None
        package = ModuleType("services")
        package.__path__ = []
        pages = ModuleType("services.mpw_trx_public_pages")
        pages.product_checkout = self.guest_view
        self.modules = patch.dict(sys.modules, {
            "services": package,
            "services.mpw_trx_public_pages": pages,
        })
        self.modules.start()

    def tearDown(self):
        self.modules.stop()

    def match(self, *, name="mpw_trx_public_product", view=None,
              namespaces=()):
        return SimpleNamespace(
            url_name=name, namespaces=namespaces,
            func=self.guest_view if view is None else view,
        )

    def test_effective_route_accepts_exact_patched_guest_view(self):
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/") as reverse, patch(
            "django.urls.resolve", return_value=self.match(),
        ) as resolve:
            self.assertEqual(verified_guest_checkout_url(901),
                             "/commerce/book/901/")
        reverse.assert_called_once_with(
            "mpw_trx_public_product", kwargs={"product_id": 901})
        resolve.assert_called_once_with("/commerce/book/901/")

    def test_shadowed_legacy_name_is_not_accepted(self):
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/"), patch(
            "django.urls.resolve",
            return_value=self.match(name="book", namespaces=("mpw_commerce",)),
        ):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_same_path_bound_to_different_callable_is_not_accepted(self):
        wrong_view = lambda request, product_id: None
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/"), patch(
            "django.urls.resolve", return_value=self.match(view=wrong_view),
        ):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_same_path_under_another_namespace_is_not_accepted(self):
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/"), patch(
            "django.urls.resolve",
            return_value=self.match(namespaces=("untrusted",)),
        ):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_reverse_cannot_point_at_foreign_url_or_account_route(self):
        for uri in (
            "https://external.example/commerce/book/901/",
            "//external.example/commerce/book/901/",
            "/accounts/login/",
            "/commerce/book/900/",
            "/commerce/book/901/?redirect=evil",
        ):
            with self.subTest(uri=uri), patch(
                "django.urls.reverse", return_value=uri,
            ):
                self.assertIsNone(verified_guest_checkout_url(901))

    def test_invalid_boolean_or_string_product_id_cannot_construct_route(self):
        for value in (True, False, None, 0, -3, "901", 1.5):
            with self.subTest(id=value), patch("django.urls.reverse") as rev:
                self.assertIsNone(verified_guest_checkout_url(value))
                rev.assert_not_called()

    def test_missing_registered_guest_route_fails_closed(self):
        with patch("django.urls.reverse",
                   side_effect=NoReverseMatch("guest view absent")):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_reverse_success_but_resolve_failure_fails_closed(self):
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/"), patch(
            "django.urls.resolve", side_effect=Resolver404({"path": "blocked"}),
        ):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_imported_guest_view_must_be_current_effective_callable(self):
        pages = sys.modules["services.mpw_trx_public_pages"]
        pages.product_checkout = lambda request, product_id: None
        with patch("django.urls.reverse",
                   return_value="/commerce/book/901/"), patch(
            "django.urls.resolve", return_value=self.match(),
        ):
            self.assertIsNone(verified_guest_checkout_url(901))

    def test_missing_guest_module_even_with_matching_path_fails_closed(self):
        with patch.dict(sys.modules, {
            "services.mpw_trx_public_pages": None,
        }), patch("django.urls.reverse", return_value="/commerce/book/901/"):
            self.assertIsNone(verified_guest_checkout_url(901))


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "evil.example"])
class BrokenGatewayAvailabilityTests(SimpleTestCase):
    def test_release_provider_failure_does_not_make_store_unavailable(self):
        package = ModuleType("services")
        package.__path__ = []
        context = ModuleType("services.mpw_trx_commercial_context")
        catalog = ModuleType("services.mpw_trx_public_catalog")

        def crashing_flags(request):
            raise ValueError("malformed protected release proof")

        context.checkout_flags = crashing_flags
        catalog.public_trx_catalog = lambda after_id: ([], False)
        catalog.public_trx_product = lambda product_id: None
        request = RequestFactory().get(
            "/store/", secure=True, HTTP_HOST="mojplaywin.com")
        with patch.dict(sys.modules, {
            "services": package,
            "services.mpw_trx_commercial_context": context,
            "services.mpw_trx_public_catalog": catalog,
        }):
            self.assertIsNone(_verified_private_gateway(request))
            self.assertEqual(approved_cards(request), ((), None))
