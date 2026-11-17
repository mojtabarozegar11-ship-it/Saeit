"""Real Django HTTP and SEO regression coverage for twenty + Persian locale paths."""
from pathlib import Path
import xml.etree.ElementTree as ET
from django.test import SimpleTestCase, override_settings
from django.utils.html import escape

from core.world20_views import _RANKED, _SUPPLEMENT, _RTL, world_catalog


@override_settings(ALLOWED_HOSTS=[
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver",
], ROOT_URLCONF="config.world20_ci_urls")
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
                self.assertIn(escape(metadata["contact_label"]), text)
                self.assertIn('href="/world/' + code + '/moj-prop-interest/"', text)
                self.assertIn("mailto:mojplaywin@gmail.com?subject=MOJ-PROP-01%20information%20request", text)
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
        theme = (base / "core/templates/mojplaywin/theme.html").read_text("utf-8")
        self.assertIn('href="/moj-prop/" aria-label="MOJ PROP challenge information"', theme)
        self.assertIn('href="/world/" aria-label="Choose world languages"', theme)
        homepage = (base / "core/templates/mojplaywin/home.html").read_text("utf-8")
        self.assertIn('Explore MOJ PROP challenges', homepage)
        self.assertIn('20 world languages + Persian', homepage)
        self.assertIn('Moj Prop', (base / "core/world20_catalog.json").read_text("utf-8"))

    def test_08_host_scoped_sitemap_contains_exact_21_language_urls(self):
        response = self.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"].split(";")[0], "application/xml")
        root = ET.fromstring(response.content)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
              "x": "http://www.w3.org/1999/xhtml"}
        urls = root.findall("s:url", ns)
        self.assertEqual(len(urls), 30)
        locs = [item.find("s:loc", ns).text for item in urls]
        self.assertEqual(len(locs), len(set(locs)))
        self.assertIn("https://mojplaywin.com/moj-prop/", locs)
        self.assertIn("https://mojplaywin.com/world/", locs)
        for lang in _RANKED + _SUPPLEMENT:
            url = "https://mojplaywin.com/world/" + lang + "/"
            self.assertIn(url, locs)
            entry = urls[locs.index(url)]
            alternate = entry.findall("x:link", ns)
            self.assertEqual(len(alternate), 22)
            self.assertIn(("x-default", "https://mojplaywin.com/world/"),
                          [(x.attrib["hreflang"], x.attrib["href"]) for x in alternate])
        self.assertFalse(any("zomorodmelal.ir" in loc for loc in locs))
        self.assertEqual(self.client.get(
            "/sitemap.xml", secure=True, HTTP_HOST="zomorodmelal.ir").status_code, 404)

    def test_09_robots_points_at_mojplaywin_and_excludes_private_client_data(self):
        response = self.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8")
        self.assertIn("Sitemap: https://mojplaywin.com/sitemap.xml", body)
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Disallow: /moj-prop-v141/statement/", body)
        self.assertNotIn("Sitemap: https://zomorodmelal.ir", body)
        self.assertEqual(self.client.get(
            "/robots.txt", secure=False, HTTP_HOST=self.HOST).status_code, 404)

    def test_10_existing_company_sitemap_and_robots_are_preserved_by_host(self):
        source = (Path(__file__).resolve().parents[1] /
                  "core/seo_views.py").read_text("utf-8")
        self.assertIn("return mojplaywin_world_sitemap(request)", source)
        self.assertIn("return mojplaywin_world_robots(request)", source)
        self.assertIn('https://zomorodmelal.ir', source)

    def test_11_all_21_native_forms_have_same_backend_consent_contract(self):
        for code in _RANKED + _SUPPLEMENT:
            with self.subTest(code=code):
                resp = self.get(f"/world/{code}/moj-prop-interest/")
                self.assertEqual(resp.status_code, 200)
                text = resp.content.decode("utf-8")
                locale = world_catalog()["locales"][code]
                self.assertIn("no-store", resp["Cache-Control"])
                self.assertEqual(resp["X-Robots-Tag"], "noindex, nofollow, noarchive")
                self.assertIn("frame-ancestors 'none'", resp["Content-Security-Policy"])
                self.assertIn(f'lang="{code}" dir="{locale["direction"]}"', text)
                self.assertIn(escape(locale["lead"]["name"]), text)
                self.assertIn(escape(locale["lead"]["email"]), text)
                self.assertIn(escape(locale["lead"]["consent"]), text)
                self.assertIn(escape(locale["lead"]["submit"]), text)
                self.assertIn(escape(locale["lead"]["receipt"]), text)
                self.assertIn('action="/world/' + code + '/moj-prop-interest/"', text)
                for field in ("csrfmiddlewaretoken", "name", "email", "service",
                              "horizon", "website", "idempotency_key",
                              "notes", "consent"):
                    self.assertIn('name="' + field + '"', text)
                self.assertIn('name="service" value="blueprint"', text)
                self.assertIn('name="horizon" value="review"', text)
                self.assertIn("Prelaunch interest only: MOJ-PROP-01", text)
                self.assertNotIn('name="wallet_address"', text)
                self.assertNotIn('name="amount"', text)
                self.assertNotIn('name="order_id"', text)

    def test_12_native_form_rejects_unsafe_domains_methods_and_locale_query(self):
        from django.test import Client
        for path in ("/world/zz/moj-prop-interest/",
                     "/world/fa/moj-prop-interest/?email=x",
                     "/world/fa/moj-prop-interest/?lang=hi"):
            self.assertEqual(self.get(path).status_code, 404)
        # CSRF fails closed before the locale form can write a lead.
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(
            "/world/fa/moj-prop-interest/", secure=True,
            HTTP_HOST=self.HOST).status_code, 403)
        for method in (self.client.patch, self.client.put, self.client.delete):
            response = method("/world/fa/moj-prop-interest/",
                              secure=True, HTTP_HOST=self.HOST)
            self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.get(
            "/world/fa/moj-prop-interest/",
            secure=False, HTTP_HOST=self.HOST).status_code, 404)
        self.assertEqual(self.client.get(
            "/world/fa/moj-prop-interest/",
            secure=True, HTTP_HOST="zomorodmelal.ir").status_code, 404)

    def test_13_native_form_head_no_body_and_source_routes_preserved(self):
        response = self.client.head(
            "/world/fa/moj-prop-interest/",
            secure=True, HTTP_HOST=self.HOST,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        urls = (Path(__file__).resolve().parents[1] /
                "config/urls.py").read_text("utf-8")
        self.assertIn('path("world/<str:lang>/moj-prop-interest/"', urls)
        self.assertIn('path("moj-prop-intake/"', urls)
        source = (Path(__file__).resolve().parents[1] /
                  "core/mojprop_views.py").read_text("utf-8")
        self.assertIn("with transaction.atomic():", source)
        self.assertIn("MojPropRequest.objects.create(", source)
        self.assertIn("def _keyed_request_id", source)
        self.assertIn('modes == ["html"]', source)

    def test_14_21_private_receipt_locales_have_complete_validated_copy(self):
        source = world_catalog()["locales"]
        names = {
            "received", "duplicate", "private_token", "failed", "status_link",
        }
        for code in _RANKED + _SUPPLEMENT:
            with self.subTest(code=code):
                fields = source[code]["lead"]
                self.assertTrue(all(k in fields and fields[k].strip()
                                    for k in names))
                self.assertNotEqual(fields["received"], fields["failed"])
        receipt = (Path(__file__).resolve().parents[1] /
                   "core/templates/mojplaywin/world20_prop_receipt.html").read_text("utf-8")
        self.assertIn('id="private-receipt"', receipt)
        self.assertIn("{{ private_receipt }}", receipt)
        self.assertIn("{{ copy.lead.received }}", receipt)
        self.assertIn("{{ copy.lead.private_token }}", receipt)
        self.assertNotIn("<script", receipt)
