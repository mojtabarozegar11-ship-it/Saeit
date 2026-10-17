"""Mobile-specific original-photo derivatives, never changes payment or protected site assets."""
from pathlib import Path
from django.test import SimpleTestCase, override_settings

from core.mojplaywin_views import VENTURES, _mobile_hero_for, _responsive_venture_cards

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "core" / "static" / "site"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinMobileImagesTests(SimpleTestCase):
    def test_resized_hero_file_exists_and_original_remains_unmodified(self):
        from scripts.mojplaywin_generate_mobile_heroes import SOURCE_NAMES, convert
        self.assertEqual(len(SOURCE_NAMES), 22)
        for name in SOURCE_NAMES:
            with self.subTest(name=name):
                original = ASSET / "heroes" / (name + ".webp")
                mobile = ASSET / "mojplaywin-atelier" / "mobile-heroes" / (name + ".webp")
                self.assertTrue(original.is_file())
                self.assertTrue(mobile.is_file())
                self.assertLess(mobile.stat().st_size, 45001)
                self.assertLess(mobile.stat().st_size, original.stat().st_size)
                before = original.read_bytes()
                result = convert(name, persist=False)
                self.assertEqual(result["mobile_bytes"], mobile.stat().st_size)
                self.assertEqual(original.read_bytes(), before)

    def test_cannot_derive_responsive_photo_path_from_foreign_or_untrusted_path(self):
        for bad in (
            "site/mojplaywin-coin-logo.png", "/mojtaba.roozegar/profile.jpg",
            "site/heroes/../../customer_secret.webp",
            "site/heroes/fake.webp", "site/heroes/farnaz.webp",
            "site/mojplaywin-atelier/digital-products.svg",
            None,
        ):
            with self.subTest(bad=bad):
                self.assertEqual(_mobile_hero_for(bad), "")
        self.assertEqual(
            _mobile_hero_for("site/heroes/agriculture.webp"),
            "site/mojplaywin-atelier/mobile-heroes/agriculture.webp",
        )

    def test_main_site_context_uses_new_field_without_mutating_original_ventures(self):
        old = [dict(x) for x in VENTURES]
        displayed = _responsive_venture_cards()
        self.assertEqual(len(displayed), len(VENTURES))
        self.assertTrue(all(x["mobile_image"].endswith(".webp") for x in displayed))
        self.assertEqual(VENTURES, old)
        self.assertTrue(all("mobile_image" not in x for x in VENTURES))

    def test_main_site_templates_use_mobile_sources_preserve_original_image_tag(self):
        source = (ROOT / "core/templates/mojplaywin/section.html").read_text(encoding="utf-8")
        self.assertIn("{% static section_mobile_image %}", source)
        self.assertIn("{% static section_image %}", source)
        self.assertIn("{% static item.mobile_image %}", source)
        self.assertIn("{% static item.image %}", source)
        self.assertIn("max-width: 700px", source)

    def test_main_domain_section_renders_original_and_mobile_sources(self):
        response = self.client.get("/ventures/agriculture/", HTTP_HOST="mojplaywin.com")
        self.assertEqual(response.status_code, 200)
        source = response.content.decode("utf-8")
        self.assertIn("mojplaywin-atelier/mobile-heroes/agriculture.", source)
        self.assertIn("site/heroes/agriculture.", source)
        self.assertIn("mojplaywin-atelier/mobile-heroes/marketplace.", source)

    def test_zomorod_domain_never_renders_branded_venture_pages(self):
        response = self.client.get("/ventures/agriculture/", HTTP_HOST="zomorodmelal.ir")
        self.assertEqual(response.status_code, 404)
