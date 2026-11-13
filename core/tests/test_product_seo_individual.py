import json
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from core.models import Product


@override_settings(ALLOWED_HOSTS=["testserver","zomorodmelal.ir","mojplaywin.com"])
class ProductSeoTests(TestCase):
    def create_product(self, active=True, metadata=None):
        return Product.objects.create(title="کتاب آموزش علمی کشاورزی",product_type="Digital_Book",
                                      price="12.50",currency="USD",active=active,
                                      metadata=metadata or {"description":"راهنمای مستند و کاربردی"})

    def test_active_product_has_independent_page_and_schema(self):
        p=self.create_product()
        response=self.client.get("/store/product/{}/".format(p.pk), HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,p.title)
        self.assertContains(response,"https://zomorodmelal.ir/store/product/{}/".format(p.pk))
        self.assertContains(response,'"@type": "Product"')
        self.assertNotContains(response,'"@type": "Offer"')

    def test_inactive_products_are_not_public_or_listed_in_sitemap(self):
        p=self.create_product(active=False)
        self.assertEqual(self.client.get("/store/product/{}/".format(p.pk),HTTP_HOST="zomorodmelal.ir").status_code,404)
        sitemap=self.client.get("/sitemap.xml",HTTP_HOST="zomorodmelal.ir").content.decode()
        self.assertNotIn("/store/product/{}/".format(p.pk),sitemap)

    def test_active_product_is_listed_and_linked(self):
        p=self.create_product()
        html=self.client.get("/store/",HTTP_HOST="zomorodmelal.ir").content.decode()
        self.assertIn("/store/product/{}/".format(p.pk),html)
        xml=self.client.get("/sitemap.xml",HTTP_HOST="zomorodmelal.ir").content
        ElementTree.fromstring(xml)
        self.assertIn("/store/product/{}/".format(p.pk),xml.decode())

    def test_mojplaywin_does_not_leak_zomorod_detail_route(self):
        p=self.create_product()
        response=self.client.get("/store/product/{}/".format(p.pk),HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,404)

    def test_mojplaywin_featured_product_has_its_own_canonical_detail(self):
        product = Product.objects.create(
            pk=72, title="Original English Chess Guide",
            product_type="Digital_Book", price="7.50", currency="USD",
            active=True, metadata={"summary": "Original verified course material"},
        )
        response = self.client.get(
            "/store/product/{}/".format(product.pk), HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://mojplaywin.com/store/product/72/")
        self.assertContains(response, "<title>Original English Chess Guide | MojPlayWin Digital Store</title>", html=True)
        self.assertContains(response, 'name="description" content="Original verified course material"')
        self.assertNotContains(response, '"@type": "Offer"')

    def test_other_mojplaywin_pages_retain_their_own_seo_title(self):
        response = self.client.get("/store/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        # The store has a dedicated branded site_base.html and its own title;
        # the global base.html fallback must never override that title.
        self.assertContains(
            response,
            "<title>Chess Books, Children’s Story &amp; Website Kit | MojPlayWin</title>",
            html=True,
        )
        self.assertNotContains(
            response, "<title>Original English Chess Guide | MojPlayWin Digital Store</title>"
        )

    @override_settings(MPW_TRX_PUBLIC_PRODUCT_IDS=(991,), MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True)
    def test_approved_new_mojplaywin_sku_has_separate_public_detail(self):
        sha = "a" * 64
        product = Product.objects.create(
            pk=991, title="Approved Original Digital Tool",
            product_type="Digital_Tool", price="12.00", currency="USD",
            active=True, metadata={
                "summary": "Documented original digital tool",
                "rights_cleared": True, "publication_approved": True,
                "sha256": sha, "rights_asset_sha256": sha,
                "rights_document_sha256": "b" * 64,
            },
        )
        response = self.client.get(
            "/store/product/{}/".format(product.pk), HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://mojplaywin.com/store/product/991/")
        # Owning the product and enabling the switch do NOT prove the
        # verified guest payment handler has been installed on cPanel.
        self.assertNotContains(response, '"@type": "Offer"')
        self.assertContains(response, "secure TRX checkout is not yet verified")

    @override_settings(MPW_TRX_PUBLIC_PRODUCT_IDS=(991,), MPW_WALLETLESS_TRX_PUBLIC_ENABLED=True)
    def test_reviewed_checkout_route_allows_owner_approved_offer(self):
        from unittest.mock import patch
        sha = "a" * 64
        product = Product.objects.create(
            pk=991, title="Approved Original Digital Tool",
            product_type="Digital_Tool", price="12.00", currency="USD",
            active=True, metadata={
                "summary": "Documented original digital tool",
                "rights_cleared": True, "publication_approved": True,
                "sha256": sha, "rights_asset_sha256": sha,
                "rights_document_sha256": "b" * 64,
            },
        )
        # This stub checks only the positive SEO rendering contract, NOT
        # live checkout readiness, ledger settlement, or paid file access.
        with patch(
            "core.product_seo_views.approved_guest_checkout_route",
            return_value="/store/product/991/checkout/",
        ) as route:
            response = self.client.get(
                "/store/product/991/", HTTP_HOST="mojplaywin.com"
            )
        self.assertEqual(response.status_code, 200)
        route.assert_called_once_with(product.pk)
        self.assertContains(response, '"@type": "Offer"')
        self.assertContains(response, '"priceCurrency": "USD"')

    @override_settings(MPW_TRX_PUBLIC_PRODUCT_IDS=(991,), MPW_WALLETLESS_TRX_PUBLIC_ENABLED=False)
    def test_mojplaywin_payment_disabled_never_advertises_purchase_offer(self):
        sha = "a" * 64
        product = Product.objects.create(
            pk=991, title="Owner-approved Digital Guide",
            product_type="Digital_Book", price="12.00", currency="USD",
            active=True, metadata={
                "rights_cleared": True, "publication_approved": True,
                "sha256": sha, "rights_asset_sha256": sha,
                "rights_document_sha256": "b" * 64,
            },
        )
        response = self.client.get(
            "/store/product/991/", HTTP_HOST="mojplaywin.com"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '"@type": "Offer"')
        self.assertContains(response, "verified checkout is not yet available")

    def test_explicit_sale_status_allows_offer_schema(self):
        p=self.create_product(metadata={"sales_enabled":True,"in_stock":True,"seo_description":"کتاب آموزشی"})
        response=self.client.get("/store/product/{}/".format(p.pk),HTTP_HOST="zomorodmelal.ir")
        self.assertContains(response,'"@type": "Offer"')
        self.assertContains(response,'"priceCurrency": "USD"')
