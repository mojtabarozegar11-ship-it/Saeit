from django.test import SimpleTestCase
from django.urls import resolve

from core.mojplaywin_section_catalog import SECTIONS
from core.mojplaywin_section_views import section_page


class MojPlayWinSectionArchitectureTests(SimpleTestCase):
    def test_nine_sections_have_distinct_metadata(self):
        self.assertEqual(len(SECTIONS), 9)
        self.assertEqual(len({entry['title'] for entry in SECTIONS.values()}), 9)
        for slug, entry in SECTIONS.items():
            with self.subTest(slug=slug):
                self.assertTrue(entry['description'])
                self.assertGreaterEqual(len(entry['cards']), 3)
                self.assertEqual(len({card[0] for card in entry['cards']}), len(entry['cards']))

    def test_six_new_routes(self):
        for slug in ('markets', 'marketing', 'gold-jewelry', 'stocks', 'real-estate', 'encyclopedia'):
            with self.subTest(slug=slug):
                match = resolve('/' + slug + '/')
                self.assertIs(match.func, section_page)

    def test_existing_route_names_are_retained(self):
        for path in ('/economy/', '/research/', '/education/', '/ai/', '/studio/'):
            with self.subTest(path=path):
                self.assertIsNotNone(resolve(path))
