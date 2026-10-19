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

    def test_legacy_emerald_css_is_present_and_scoped_to_main_site(self):
        from django.contrib.staticfiles.finders import find
        source_path = find("site/emerald-system.css")
        self.assertIsNotNone(source_path)
        css = Path(source_path).read_text(encoding="utf-8")
        self.assertIn("body.zomorod-olive-site", css)
        self.assertIn("focus-visible", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertGreater(len(css), 2000)

    def test_luxury_design_stays_scoped_to_zomorod_and_has_accessibility(self):
        css = (ROOT / "core/static/site/zomorod-expert-sections-v1.css").read_text(
            encoding="utf-8"
        )
        self.assertIn("body.zomorod-olive-site.services-page", css)
        self.assertNotIn("body.services-page", css)
        for required in (
            "@container", "container-type:inline-size", "text-wrap:balance",
            "color-mix", "prefers-reduced-motion", "min-height:44px",
        ):
            with self.subTest(css_feature=required):
                self.assertIn(required, css)
