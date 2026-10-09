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

@override_settings(ALLOWED_HOSTS=["zomorodmelal.ir", "mojplaywin.com", "www.mojplaywin.com", "testserver"])
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

    def test_store_does_not_publish_unverified_or_other_brand_inventory(self):
        from core.models import KnowledgeArticle, Product
        unpublished = KnowledgeArticle.objects.create(
            title="Draft listing", slug="mpw-draft-listing", content="Not released.", published=False
        )
        published = KnowledgeArticle.objects.create(
            title="Other brand listing", slug="mpw-other-brand-listing",
            content="Published elsewhere.", published=True
        )
        Product.objects.create(
            title="Unreleased MojPlayWin Product", product_type="digital", active=True,
            knowledge_article=unpublished, metadata={"brand_code": "mojplaywin"}
        )
        Product.objects.create(
            title="Other Brand Product", product_type="digital", active=True,
            knowledge_article=published, metadata={"brand_code": "other"}
        )
        response = self.client.get("/store/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Unreleased MojPlayWin Product")
        self.assertNotContains(response, "Other Brand Product")
        self.assertContains(response, "No public products yet.")

    def test_store_renders_product_title(self):
        from core.models import KnowledgeArticle, Product
        article = KnowledgeArticle.objects.create(title="Verified Tool documentation", slug="verified-tool-documentation", content="Published product information.", published=True)
        product=Product.objects.create(title="Verified Tool",product_type="digital",price=10,currency="USD",active=True,knowledge_article=article,metadata={"summary":"Useful verified tool.", "brand_code": "mojplaywin"})
        response=self.client.get("/store/",HTTP_HOST="mojplaywin.com")
        self.assertContains(response,"Verified Tool")
        self.assertContains(response,"Useful verified tool.")
        self.assertContains(response,f"/store/product/{product.pk}/")

class BusinessArchitectureTests(TestCase):
    def test_seeded_games_are_us_first(self):
        from core.models import BusinessUnit, MarketPolicy
        games=BusinessUnit.objects.get(code="games")
        self.assertEqual(games.primary_market,"US")
        self.assertFalse(games.global_scope)
        self.assertTrue(MarketPolicy.objects.filter(business_unit=games,market_code="US",role="primary").exists())

    def test_global_services_are_marked_global(self):
        from core.models import BusinessUnit
        services=BusinessUnit.objects.get(code="services")
        self.assertTrue(services.global_scope)
        self.assertEqual(services.primary_market,"GLOBAL")

    def test_no_canadian_legal_entity_is_fabricated(self):
        from core.models import LegalEntity
        self.assertFalse(LegalEntity.objects.filter(jurisdiction__iexact="CA").exists())

