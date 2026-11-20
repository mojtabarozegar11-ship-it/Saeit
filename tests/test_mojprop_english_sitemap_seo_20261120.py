"""English Moj Prop sitemap contract: public informational routes only."""
from xml.etree import ElementTree

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.seo_views import sitemap_xml


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com"])
class MojPropEnglishSitemapTests(SimpleTestCase):
    def test_canonical_public_urls_on_both_hosts(self):
        expected = {
            "https://mojplaywin.com/",
            "https://mojplaywin.com/store/",
            "https://mojplaywin.com/moj-prop/",
            "https://mojplaywin.com/moj-prop/starter-30-trx/",
            "https://mojplaywin.com/moj-prop/rules/",
            "https://mojplaywin.com/moj-prop/signals/",
            "https://mojplaywin.com/moj-prop/payment/",
            "https://mojplaywin.com/moj-prop/contact/",
        }
        for host in ("mojplaywin.com", "www.mojplaywin.com"):
            with self.subTest(host=host):
                response = sitemap_xml(RequestFactory().get("/sitemap.xml", HTTP_HOST=host))
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/xml", response["Content-Type"])
                root = ElementTree.fromstring(response.content)
                urls = [n.text for n in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
                self.assertEqual(set(urls), expected)
                self.assertEqual(len(urls), len(expected))
                self.assertFalse(any("checkout" in u or "status" in u or "?" in u for u in urls))
