"""Canonical global game catalog source must preserve original site sections."""
import pathlib
import unittest

PAGE=pathlib.Path(__file__).resolve().parents[1]/"core/templates/brands/mojplaywin/page.html"
MARKER='id="mpw-global-living-cities-feature-20261101"'

class MojPlayWinGlobalGamesCatalogTests(unittest.TestCase):
    def test_game_card_only_on_games_template_branch(self):
        html=PAGE.read_text(encoding="utf-8")
        self.assertEqual(html.count(MARKER),1)
        self.assertEqual(html.count('href="/living-cities/play/"'),1)
        self.assertIn('{% if page_key == \'games\' %}',html)
        self.assertTrue(html.index('{% if page_key == \'games\' %}') < html.index(MARKER))
        self.assertLess(html.index(MARKER),html.index("{% endif %}",html.index(MARKER)))
        self.assertIn("English by default",html)
        self.assertIn("200 missions",html)
        self.assertIn("20 world regions",html)
        self.assertIn("Local browser save",html)

    def test_preexisting_games_and_site_content_not_removed(self):
        html=PAGE.read_text(encoding="utf-8")
        self.assertIn("Pulse Forge",html)
        self.assertIn("Beacon Labyrinth",html)
        self.assertIn("Cipher Garden",html)
        self.assertIn("Skyline Keeper",html)
        self.assertIn("Nebula Salvage",html)
        self.assertIn("/games/first-realm/",html)
        self.assertIn("{% if page_key == 'about' %}",html)
        self.assertIn("{% if page_key == 'studio' %}",html)

if __name__=="__main__":
    unittest.main()
