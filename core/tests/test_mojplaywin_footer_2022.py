"""Copyright footer year for MojPlayWin only; preserve Django and other site content."""
from pathlib import Path

from django.test import TestCase, override_settings

ROOT = Path(__file__).resolve().parents[2]
COPYRIGHT = "© 2022 MojPlayWin. All rights reserved."


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinFooter2022Tests(TestCase):
    def test_both_owned_site_footers_use_fixed_2022(self):
        for path in (
            "core/templates/mojplaywin/footer.html",
            "core/templates/brands/mojplaywin/base.html",
        ):
            with self.subTest(path=path):
                content = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn(COPYRIGHT, content)
                self.assertNotIn("© 2024 MojPlayWin", content)
                self.assertNotIn("© 2026 MojPlayWin", content)

    def test_real_main_site_pages_show_2022(self):
        for path in ("/", "/store/", "/research/", "/ventures/agriculture/"):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(response.status_code, 200)
                self.assertIn(COPYRIGHT, response.content.decode("utf-8"))

    def test_does_not_change_zomorod_templates(self):
        self.assertNotIn(
            "Zomorod",
            (ROOT / "core/templates/mojplaywin/footer.html").read_text(encoding="utf-8"),
        )
