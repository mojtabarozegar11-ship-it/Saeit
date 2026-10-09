from django.test import TestCase, override_settings
from core.models import KnowledgeArticle, Product


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinSitemapSafetyTests(TestCase):
    def test_specialty_drafts_not_in_sitemap(self):
        response = self.client.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"/products/software-products/", response.content)
        self.assertNotIn(b"/services/seo-services/", response.content)

    def test_other_brand_and_unpublished_products_are_excluded(self):
        other_article = KnowledgeArticle.objects.create(
            title="Unreleased cross-brand article", slug="unreleased-cross-brand-sitemap",
            content="Internal testing only", published=False,
        )
        other_product = Product.objects.create(
            title="Unreleased cross-brand product", product_type="digital", knowledge_article=other_article,
            active=True, metadata={"brand_code": "another-brand"},
        )
        response = self.client.get("/sitemap.xml", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(f"/store/product/{other_product.pk}/".encode(), response.content)
