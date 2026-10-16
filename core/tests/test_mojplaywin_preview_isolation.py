"""Isolated previews only: no change to production URL routing or any protected site."""
from django.conf import settings
from django.test import SimpleTestCase, override_settings


@override_settings(
    ROOT_URLCONF="core.mojplaywin_atelier_preview_urls",
    ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver"],
)
class MojPlayWinPreviewIsolationTests(SimpleTestCase):
    def test_preview_only_pages_render_original_specialty_content(self):
        for path, title, marker in (
            ("/ai/", "Artificial Intelligence", "mojplaywin-atelier/ai-workflow."),
            ("/blockchain/", "Blockchain & Web3", "blockchain-network.svg"),
            ("/support/", "MojPlayWin Support", "mpw-support-handbook"),
        ):
            with self.subTest(path=path):
                r = self.client.get(path, HTTP_HOST="mojplaywin.com")
                self.assertEqual(r.status_code, 200)
                html = r.content.decode("utf-8")
                self.assertIn(title, html)
                self.assertIn(marker, html)
                self.assertIn('href="https://mojplaywin.com' + path + '"', html)
                self.assertIn('class="mpw-atelier-v4"', html)

    def test_legacy_preview_pages_never_render_on_zomorod_host(self):
        for path in ("/ai/", "/blockchain/", "/support/"):
            with self.subTest(path=path):
                r = self.client.get(path, HTTP_HOST="zomorodmelal.ir")
                self.assertEqual(r.status_code, 404)

    def test_preview_urlconf_is_not_global_runtime_setting(self):
        self.assertEqual(settings.ROOT_URLCONF, "core.mojplaywin_atelier_preview_urls")
        source = __import__("pathlib").Path(__file__).resolve().parents[2] / "config" / "settings.py"
        self.assertNotIn('"core.mojplaywin_atelier_preview_urls"', source.read_text(encoding="utf-8"))
