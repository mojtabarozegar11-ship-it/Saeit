from django.test import RequestFactory, TestCase, override_settings
from core.brand import brand_for_request
from core.brand_views import branded_home
from core.brand_seo_views import branded_robots_txt, branded_sitemap_xml
from core.models import BrandSite

@override_settings(ALLOWED_HOSTS=["zomorodmelal.ir", "mojplaywin.com", "www.mojplaywin.com", "www.future.example", "testserver"])
class MultiBrandRoutingTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_mojplaywin_host_resolves_independent_brand(self):
        request = self.rf.get("/", HTTP_HOST="mojplaywin.com")
        brand = brand_for_request(request)
        self.assertIsNotNone(brand)
        self.assertEqual(brand.code, "mojplaywin")
        self.assertEqual(brand.template, "brands/mojplaywin/home.html")

    def test_mojplaywin_home_uses_english_independent_template(self):
        response = branded_home(self.rf.get("/", HTTP_HOST="mojplaywin.com"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("MojPlayWin", body)
        self.assertIn("Own the next move.", body)
        self.assertNotIn("Zomorodmelal", body)

    def test_primary_brand_keeps_existing_home(self):
        response = branded_home(self.rf.get("/", HTTP_HOST="zomorodmelal.ir"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Zomorodmelal", response.content.decode("utf-8"))

    def test_mojplaywin_robots_and_sitemap_are_domain_correct(self):
        request = self.rf.get("/robots.txt", HTTP_HOST="mojplaywin.com")
        robots = branded_robots_txt(request).content.decode("utf-8")
        self.assertIn("https://mojplaywin.com/sitemap.xml", robots)
        self.assertNotIn("zomorodmelal.ir", robots)
        sitemap = branded_sitemap_xml(self.rf.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")).content.decode("utf-8")
        self.assertIn("https://mojplaywin.com/", sitemap)
        self.assertIn("https://mojplaywin.com/store/", sitemap)
        self.assertIn("https://mojplaywin.com/crypto-payments/", sitemap)
        self.assertIn("https://mojplaywin.com/canada-vision/", sitemap)
        self.assertNotIn("zomorodmelal.ir", sitemap)

    def test_database_brand_alias_resolves_without_code_change(self):
        BrandSite.objects.create(
            code="futurebrand", name="Future Brand", primary_domain="future.example",
            aliases=["www.future.example"], default_language="en", direction="ltr",
            theme_key="mojplaywin", active=True,
        )
        brand = brand_for_request(self.rf.get("/", HTTP_HOST="www.future.example"))
        self.assertEqual(brand.code, "futurebrand")
        self.assertEqual(brand.domain, "future.example")

class MojPlayWinRevenueRoutingTests(TestCase):
    def test_zomorod_agriculture_is_not_shadowed_by_brand_router(self):
        response=self.client.get("/agriculture/", HTTP_HOST="zomorodmelal.ir")
        self.assertNotEqual(response.status_code,404)

    def test_mojplaywin_revenue_pages_resolve(self):
        for path in ("/products/","/services/","/ai/","/software/","/commerce/","/blockchain/","/crypto-payments/","/global-business/","/agro-industry/","/canada-vision/"):
            response=self.client.get(path,HTTP_HOST="mojplaywin.com")
            self.assertEqual(response.status_code,200,path)

    def test_mojplaywin_store_uses_real_inventory_and_empty_state(self):
        response=self.client.get("/store/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"GLOBAL / STORE")
        self.assertContains(response,"No public products yet.")

    def test_product_detail_rejects_inactive_inventory(self):
        from core.models import Product
        product=Product.objects.create(title="Private draft",product_type="digital",active=False)
        response=self.client.get(f"/store/product/{product.pk}/",HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code,404)

    def test_zomorod_services_preserved(self):
        response=self.client.get("/services/",HTTP_HOST="zomorodmelal.ir")
        self.assertNotEqual(response.status_code,404)
