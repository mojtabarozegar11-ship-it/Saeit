from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

BASE_DIR = Path(__file__).resolve().parents[2]


class ZomorodAgriculturePageTests(SimpleTestCase):
    def test_agriculture_index_is_served(self):
        response = self.client.get(reverse("agriculture"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("saeit-zomorod-agriculture-v1", response.content.decode())
        self.assertIn("text/html", response["Content-Type"])

    def test_agriculture_guide_is_served(self):
        response = self.client.get(reverse("agriculture_guide", kwargs={"slug": "livestock"}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("دامپروری", response.content.decode())

    def test_genetics_and_breeding_guide_is_served(self):
        response = self.client.get(reverse("agriculture_guide", kwargs={"slug": "genetics"}))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("ژنتیک و اصلاح نژاد", content)
        self.assertGreaterEqual(content.count('<section class="section"'), 10)
        for index in range(1, 13):
            self.assertIn(f"/company/genetics-{index}/", content)

    def test_unknown_agriculture_guide_is_not_exposed(self):
        response = self.client.get("/agriculture/not-a-guide/")
        self.assertEqual(response.status_code, 404)

    def test_hero_image_endpoints_return_webp(self):
        image = BASE_DIR / "core" / "static" / "site" / "heroes" / "agriculture.webp"
        if not image.is_file():
            self.skipTest("Agriculture hero asset is not included in this checkout")
        for url in (
            "/agriculture/assets/zomorod-olive-v1/agriculture.webp",
            "/amozeshgah/assets/zomorod-education-v1/agriculture.webp",
            "/static/site/heroes/agriculture.webp",
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/webp")
                self.assertTrue(response.streaming)
                self.assertIn("public", response["Cache-Control"].lower())
