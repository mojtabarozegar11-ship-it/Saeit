"""MojPlayWin-only long-form content preservation and route regression tests."""
from pathlib import Path
from unittest.mock import patch

from django.http import Http404
from django.urls import resolve
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.mojplaywin_page_content import EDITORIAL_PAGES
from core.mojplaywin_views import SECTIONS, VENTURES, platform_section, venture

ROOT = Path(__file__).resolve().parents[2]


@override_settings(ALLOWED_HOSTS=["testserver", "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir"])
class MojPlayWinCompleteSectionsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()

    def test_all_existing_main_sections_and_ventures_have_unique_complete_content(self):
        expected = set(SECTIONS) | {f"venture:{v['slug']}" for v in VENTURES}
        self.assertEqual(set(EDITORIAL_PAGES), expected)
        self.assertEqual(len(expected), 17)
        intros = set()
        for name, page in EDITORIAL_PAGES.items():
            with self.subTest(name=name):
                self.assertGreaterEqual(len(page["intro"]), 130)
                self.assertNotIn(page["intro"], intros)
                intros.add(page["intro"])
                self.assertEqual(len(page["chapters"]), 3)
                self.assertEqual(len(page["faqs"]), 2)
                self.assertGreaterEqual(len(page["links"]), 2)
                for chapter in page["chapters"]:
                    self.assertGreater(len(chapter["text"]), 120)
                    self.assertEqual(len(chapter["steps"]), 3)
                    self.assertTrue(all(len(x) > 22 for x in chapter["steps"]))
                for faq in page["faqs"]:
                    self.assertGreater(len(faq["question"]), 12)
                    self.assertGreater(len(faq["answer"]), 50)
                for link in page["links"]:
                    self.assertTrue(link["url"].startswith("/") and not link["url"].startswith("//"))
                    self.assertNotIn("/mojtaba.roozegar/", link["url"])
                    self.assertNotIn("/picm/", link["url"])

    def test_views_pass_full_content_through_existing_routes(self):
        request = self.factory.get("/research/", HTTP_HOST="mojplaywin.com")
        with patch("core.mojplaywin_views.render", side_effect=lambda req, tpl, ctx: (tpl, ctx)):
            for name in SECTIONS:
                with self.subTest(section=name):
                    template, context = platform_section(request, name)
                    self.assertEqual(template, "mojplaywin/section.html")
                    self.assertIs(context["page_content"], EDITORIAL_PAGES[name])
                    self.assertTrue(context["cards"])
            for item in VENTURES:
                with self.subTest(venture=item["slug"]):
                    template, context = venture(request, item["slug"])
                    self.assertEqual(template, "mojplaywin/section.html")
                    self.assertIs(context["page_content"], EDITORIAL_PAGES[f"venture:{item['slug']}"])
                    self.assertEqual(context["active_venture"], item["slug"])

    def test_all_17_routes_are_reachable_through_the_original_urlconf(self):
        # Verify existing routing WITHOUT modifying shared Django routes or
        # entering an independent child site or privileged production endpoint.
        routes = {
            "agriculture": "/agriculture/",
            "industry": "/industry/",
            "research": "/research/",
            "knowledge": "/knowledge/",
            "economy": "/economy/",
            "studio": "/studio/",
            "market": "/market/",
            "agents": "/agents/",
            "company": "/company/",
        }
        routes.update({f"venture:{v['slug']}": v["url"] for v in VENTURES})
        self.assertEqual(len(routes), 17)
        with patch("core.mojplaywin_views.render", side_effect=lambda req, tpl, ctx: (tpl, ctx)):
            for key, path in routes.items():
                with self.subTest(key=key, path=path):
                    match = resolve(path)
                    request = self.factory.get(path, HTTP_HOST="mojplaywin.com")
                    template, context = match.func(request, **match.kwargs)
                    self.assertEqual(template, "mojplaywin/section.html")
                    self.assertIs(context["page_content"], EDITORIAL_PAGES[key])
                    self.assertIn("section_image", context)

    def test_all_venture_images_are_distinct_and_exist(self):
        all_images = [entry["image"] for entry in VENTURES]
        all_images += [section[2] for section in SECTIONS.values()]
        self.assertEqual(len(all_images), 17)
        self.assertEqual(len(set(all_images)), 17, "Every page needs a different hero illustration")
        for filename in all_images:
            with self.subTest(filename=filename):
                self.assertTrue((ROOT / "core/static" / filename).is_file(), filename)

    def test_venture_rejects_independent_host(self):
        external_request = self.factory.get("/ventures/agriculture/", HTTP_HOST="zomorodmelal.ir")
        with self.assertRaises(Http404):
            venture(external_request, "agriculture")

    def test_template_preserves_legacy_content_and_adds_helpful_information(self):
        template = (ROOT / "core/templates/mojplaywin/section.html").read_text(encoding="utf-8")
        for required in ('{{ section_title }}', '{{ section_lead }}', 'section_image',
                         'for title,text in cards', 'section_note', 'active_venture',
                         'page_content.intro', 'for chapter in page_content.chapters',
                         'for step in chapter.steps', 'for item in page_content.faqs',
                         'for link in page_content.links', 'href="{{ link.url }}"'):
            self.assertIn(required, template)
        self.assertIn('id="mpw-editorial-{{ forloop.counter }}"', template)
        self.assertIn('href="{% if page_content %}#mpw-editorial-', template)


