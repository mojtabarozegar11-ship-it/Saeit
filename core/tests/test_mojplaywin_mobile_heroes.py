"""Mobile-specific original-photo derivatives, never changes payment or protected site assets."""
from pathlib import Path
from django.test import SimpleTestCase, override_settings

from core.mojplaywin_views import VENTURES, _mobile_hero_for, _responsive_venture_cards

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "core" / "static" / "site"


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinMobileImagesTests(SimpleTestCase):
    def test_resized_hero_file_exists_and_original_remains_unmodified(self):
        from PIL import Image
        mobile_folder = ASSET / "mojplaywin-atelier" / "mobile-heroes"
        saved = sorted(mobile_folder.glob("*.webp"))
        self.assertEqual(len(saved), 22)
        for mobile in saved:
            with self.subTest(name=mobile.name):
                original = ASSET / "heroes" / mobile.name
                self.assertTrue(original.is_file())
                self.assertLess(mobile.stat().st_size, 45001)
                self.assertLess(mobile.stat().st_size, original.stat().st_size)
                with Image.open(mobile) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertLessEqual(image.width, 560)
                    self.assertGreater(image.height, 10)
                with Image.open(original) as source:
                    self.assertGreaterEqual(source.width, 560)

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

    def test_every_editorial_gallery_keeps_originals_and_has_local_mobile_copies(self):
        from core.mojplaywin_editorial import EDITORIAL, editorial_for
        for key, specification in EDITORIAL.items():
            family, slug = key.split(":", 1)
            responsive = editorial_for(family, slug)
            self.assertIsNot(responsive, specification)
            self.assertEqual(responsive["headline"], specification["headline"])
            self.assertEqual(len(responsive["images"]), len(specification["images"]))
            for original, display in zip(specification["images"], responsive["images"]):
                with self.subTest(key=key, photo=original["path"]):
                    self.assertEqual(original["path"], display["path"])
                    self.assertEqual(original["alt"], display["alt"])
                    self.assertEqual(original["caption"], display["caption"])
                    if original["path"].startswith("site/heroes/"):
                        self.assertNotIn("mobile_path", original)
                        self.assertTrue(
                            (ROOT / "core" / "static" / display["mobile_path"]).is_file()
                        )
                    else:
                        self.assertNotIn("mobile_path", display)
        self.assertIsNone(editorial_for("missing", "not-found"))

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
