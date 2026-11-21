"""Safety and routing regression tests for the AYAR exact-path microsite."""

from django.test import SimpleTestCase
from django.urls import resolve
from django.http import Http404

from core.ayaar_views import _ALLOWED, ayaar


class AyarRoutingTests(SimpleTestCase):
    def test_home_exact_route(self):
        route = resolve("/ayaar/")
        self.assertEqual(route.func, ayaar)
        self.assertEqual(route.kwargs, {})

    def test_assets_exact_route(self):
        for filename in _ALLOWED:
            with self.subTest(filename=filename):
                route = resolve("/ayaar/" + filename)
                self.assertEqual(route.func, ayaar)
                self.assertEqual(route.kwargs, {"asset": filename})

    def test_only_expected_assets(self):
        self.assertEqual(set(_ALLOWED), {
            "index.html", "methodology.html", "styles.css", "hero.css",
            "app.js", "favicon.svg", "hero-art.svg",
        })

    def test_block_path_probes(self):
        for url in ("/ayaar/.env", "/ayaar/secret.txt", "/ayaar/admin/"):
            with self.subTest(url=url):
                try:
                    route = resolve(url)
                except Exception:
                    continue
                if route.func == ayaar:
                    from django.test import RequestFactory
                    with self.assertRaises(Http404):
                        route.func(RequestFactory().get(url), **route.kwargs)

    def test_read_only_get(self):
        from django.test import RequestFactory
        response = ayaar(RequestFactory().post("/ayaar/"))
        self.assertEqual(response.status_code, 405)
