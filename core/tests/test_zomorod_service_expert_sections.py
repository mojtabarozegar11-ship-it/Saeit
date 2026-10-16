"""Prevent content loss and fake image references in the Zomorod redesign."""
import re
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


class ZomorodServicesEditorialTests(SimpleTestCase):
    def test_old_service_sections_preserved_and_ten_new_sections_render(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        body = page.content.decode("utf-8")
        for legacy in ("services-hero", "services-grid", "services-map", "services-cta"):
            self.assertIn(legacy, body)
        self.assertEqual(body.count('<section class="zm-sector"'), 10)
        self.assertIn("زمرد ملل", body)
        self.assertIn("/agriculture/genetics/", body)
        self.assertIn("/agriculture/tools/", body)

    def test_ten_independent_local_images_are_real_files(self):
        source = (ROOT / "core/templates/core/partials/zomorod_expert_sections.html").read_text(encoding="utf-8")
        names = re.findall(r"site/heroes/([a-z-]+\.webp)", source)
        self.assertEqual(len(names), 10)
        self.assertEqual(len(set(names)), 10)
        for name in names:
            with self.subTest(image=name):
                path = ROOT / "core/static/site/heroes" / name
                self.assertTrue(path.is_file(), f"Missing editorial image: {name}")
                self.assertGreater(path.stat().st_size, 1000)

    def test_image_accessibility_and_single_subject_heading(self):
        source = (ROOT / "core/templates/core/partials/zomorod_expert_sections.html").read_text(encoding="utf-8")
        self.assertEqual(source.count('<img '), 10)
        self.assertEqual(source.count('loading="lazy"'), 10)
        self.assertEqual(source.count('alt="'), 10)
        self.assertEqual(source.count('<h2 id="zm-sector-title-'), 10)
        self.assertNotIn("قیمت قطعی", source)
