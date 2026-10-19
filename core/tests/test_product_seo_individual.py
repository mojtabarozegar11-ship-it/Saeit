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

    def test_explicit_sale_status_allows_offer_schema(self):
        p=self.create_product(metadata={"sales_enabled":True,"in_stock":True,"seo_description":"کتاب آموزشی"})
        response=self.client.get("/store/product/{}/".format(p.pk),HTTP_HOST="zomorodmelal.ir")
        self.assertContains(response,'"@type": "Offer"')
        self.assertContains(response,'"priceCurrency": "USD"')
