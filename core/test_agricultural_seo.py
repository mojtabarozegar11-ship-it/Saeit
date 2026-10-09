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


class AgriculturePillarSeoTests(SimpleTestCase):
    def test_agriculture_pillar_has_unique_search_metadata_and_internal_links(self):
        response = self.client.get("/agriculture/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("<title>کشاورزی | دانش، خدمات و فناوری کشاورزی | زمرد ملل</title>", html)
        self.assertIn('rel="canonical" href="https://zomorodmelal.ir/agriculture/"', html)
        for slug in PAGES:
            self.assertIn(f'href="/agricultural-topics/{slug}/"', html)

    def test_homepage_promotes_agriculture_and_services(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("<title>کشاورزی و خدمات کشاورزی | شرکت کشت و صنعت زمرد ملل</title>", html)
        self.assertIn('href="/agriculture/"', html)
        self.assertIn('href="/agricultural-topics/agricultural-services/"', html)

    def test_services_page_links_to_agriculture(self):
        response = self.client.get("/services/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn('href="/agriculture/"', html)
        self.assertIn('href="/agricultural-topics/agricultural-services/"', html)
