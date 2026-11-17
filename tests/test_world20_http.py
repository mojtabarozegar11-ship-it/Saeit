"""Real Django HTTP and SEO regression coverage for twenty + Persian locale paths."""
from pathlib import Path
from django.test import SimpleTestCase, override_settings
from django.utils.html import escape

from core.world20_views import _RANKED, _SUPPLEMENT, _RTL, world_catalog


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver",
])
class World20HTTPTests(SimpleTestCase):
    HOST = "mojplaywin.com"

    def get(self, path, **kwargs):
        return self.client.get(path, secure=True, HTTP_HOST=self.HOST, **kwargs)

    def test_01_exact_top20_plus_persian_speaker_rank(self):
        source = world_catalog()
        self.assertEqual(len(_RANKED), 20)
        self.assertEqual(_SUPPLEMENT, ("fa",))
        self.assertEqual(set(source["locales"]), set(_RANKED + _SUPPLEMENT))
        self.assertEqual(source["ranked_codes"], list(_RANKED))
        self.assertNotIn("fa", _RANKED)
        self.assertEqual(len(source["sections"]), 7)

    def test_02_each_language_has_independent_canonical_page_and_7_links(self):
        source = world_catalog()
        for code in _RANKED + _SUPPLEMENT:
            with self.subTest(code=code):
                resp = self.get(f"/world/{code}/")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp["Content-Language"], code)
                self.assertIn("public", resp["Cache-Control"])
                self.assertIn("frame-ancestors 'none'", resp["Content-Security-Policy"])
                text = resp.content.decode("utf-8")
                metadata = source["locales"][code]
                expected_dir = "rtl" if code in _RTL else "ltr"
                self.assertIn(f'lang="{code}" dir="{expected_dir}"', text)
                self.assertIn(escape(metadata["headline"]), text)
                self.assertIn(escape(metadata["intro"]), text)
                self.assertIn(escape(metadata["payment_notice"]), text)
                self.assertIn(escape(metadata["fallback_notice"]), text)
                self.assertIn('rel="canonical" href="https://mojplaywin.com/world/' + code + '/"', text)
                self.assertEqual(text.count('rel="alternate" hreflang='), 22)
                self.assertEqual(text.count('class="card"'), 7)
                for link in source["sections"]:
                    self.assertIn('href="' + link["url"] + '"', text)
                for code2 in _RANKED + _SUPPLEMENT:
                    self.assertIn('href="/world/' + code2 + '/"', text)
                    self.assertIn('hreflang="' + code2 + '"', text)
                self.assertNotIn("<form", text)
                self.assertNotIn("wallet_address", text)
                self.assertNotIn("sendTransaction", text)

    def test_03_default_root_and_no_auto_payment(self):
        response = self.get("/world/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], "en")
        self.assertContains(response, "https://mojplaywin.com/world/en/")
        self.assertContains(response, "No payments or funded trading accounts")
        self.assertNotContains(response, "<form")
        self.assertNotContains(response, "checkout/")

    def test_04_nonrecognized_codes_or_unexpected_query_do_not_render(self):
        for p in (
            "/world/zz/", "/world/xx/", "/world/ko/", "/world/it/",
            "/world/zh/?ref=other", "/world/?email=buyer@example.com",
            "/world/en/?lang=fa", "/world/fa/?amount=30",
        ):
            with self.subTest(path=p):
                self.assertEqual(self.get(p).status_code, 404)

    def test_05_only_https_mojplaywin_hosts(self):
        self.assertEqual(self.client.get(
            "/world/fa/", secure=False, HTTP_HOST=self.HOST).status_code, 404)
        self.assertEqual(self.client.get(
            "/world/fa/", secure=True, HTTP_HOST="zomorodmelal.ir").status_code, 404)
        self.assertEqual(self.client.get(
            "/world/fa/", secure=True, HTTP_HOST="www.mojplaywin.com").status_code, 200)

    def test_06_no_unsafe_mutating_methods_and_head_has_no_body(self):
        for method in (self.client.post, self.client.put, self.client.patch,
                       self.client.delete):
            with self.subTest(method=method.__name__):
                result = method("/world/fa/", secure=True, HTTP_HOST=self.HOST)
                self.assertEqual(result.status_code, 405)
        result = self.client.head("/world/ur/", secure=True, HTTP_HOST=self.HOST)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.content, b"")
        self.assertEqual(result["Content-Language"], "ur")

    def test_07_public_urls_and_sitewide_footer_include_world_gateway(self):
        base = Path(__file__).resolve().parents[1]
        urls = (base / "config/urls.py").read_text("utf-8")
        self.assertIn('path("world/", worldwide_index', urls)
        self.assertIn('path("world/<str:lang>/", worldwide_language', urls)
        footer = (base / "core/templates/mojplaywin/footer.html").read_text("utf-8")
        self.assertIn('href="/world/"', footer)
        self.assertIn('Moj Prop', (base / "core/world20_catalog.json").read_text("utf-8"))
