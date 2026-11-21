"""No-order, no-DB regression for actual legacy storefront checkout URLs."""
from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse

from core.mpw_legacy_guest_checkout_redirect import PUBLIC_GUEST_SKUS


@override_settings(ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class LegacyStoreCheckoutLinkTests(SimpleTestCase):
    def test_exact_three_public_product_links_have_safe_redirects(self):
        self.assertEqual(PUBLIC_GUEST_SKUS, frozenset((72, 225, 879)))
        for product_id in sorted(PUBLIC_GUEST_SKUS):
            with self.subTest(product_id=product_id):
                old_path = f"/store/product/{product_id}/checkout/"
                target = reverse("mpw_trx_checkout", kwargs={"product_id": product_id})
                self.assertEqual(target, f"/commerce/book/{product_id}/")
                resolved = resolve(old_path)
                self.assertEqual(resolved.url_name, "mpw_legacy_guest_checkout_redirect")
                response = self.client.get(old_path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], target)
                self.assertEqual(response["Cache-Control"].find("no-store") >= 0, True)

    def test_head_works_for_safe_link_previews(self):
        response = self.client.head("/store/product/225/checkout/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/commerce/book/225/")

    def test_post_is_not_forwarded_to_checkout(self):
        response = self.client.post("/store/product/225/checkout/", {"email": "not-sent@example.org"})
        self.assertEqual(response.status_code, 405)

    def test_old_query_string_is_not_replayed_or_exposed(self):
        response = self.client.get("/store/product/72/checkout/?token=private&email=secret@example.org&utm_source=referral")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/commerce/book/72/")

    def test_invalid_and_unlisted_ids_still_404(self):
        for product_id in (0, 1, 779, 999999998):
            with self.subTest(product_id=product_id):
                response = self.client.get(f"/store/product/{product_id}/checkout/")
                self.assertEqual(response.status_code, 404)

    def test_original_canonical_checkout_route_is_untouched(self):
        for product_id in PUBLIC_GUEST_SKUS:
            with self.subTest(product_id=product_id):
                target = reverse("mpw_trx_checkout", kwargs={"product_id": product_id})
                self.assertEqual(resolve(target).url_name, "mpw_trx_checkout")

    def test_product_detail_route_is_unchanged(self):
        self.assertEqual(resolve("/store/product/225/").url_name, "store_product_detail")
