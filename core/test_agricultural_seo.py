from django.test import SimpleTestCase, RequestFactory
from django.urls import resolve, reverse
from core.agricultural_seo_views import PAGES, agricultural_seo_page


class AgriculturalSeoPageTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_all_pages_have_unique_metadata_and_canonical(self):
        self.assertEqual(len(PAGES), 6)
        titles = set()
        for slug, (keyword, heading, description, sections) in PAGES.items():
            path = reverse("agricultural_seo_page", kwargs={"slug": slug})
            self.assertEqual(resolve(path).func, agricultural_seo_page)
            response = self.client.get(path, HTTP_HOST="testserver")
            self.assertEqual(response.status_code, 200)
            html = response.content.decode("utf-8")
            self.assertIn(keyword, html)
            self.assertIn('<link rel="canonical" href="https://zomorodmelal.ir' + path + '">', html)
            self.assertIn('application/ld+json', html)
            self.assertIn('name="description"', html)
            self.assertIn('lang="fa" dir="rtl"', html)
            self.assertGreaterEqual(len(sections), 3)
            titles.add(keyword)
        self.assertEqual(len(titles), len(PAGES))

    def test_unknown_topic_is_404(self):
        self.assertEqual(self.client.get("/agricultural-topics/unknown/").status_code, 404)
