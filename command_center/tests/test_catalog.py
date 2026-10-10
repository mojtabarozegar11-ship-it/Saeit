import unittest
from command_center.catalog import MODULES, AGENT_SETTINGS, localized

class CatalogTests(unittest.TestCase):
    def test_module_ids_unique(self):
        self.assertEqual(len({m[0] for m in MODULES}), len(MODULES))

    def test_both_languages_complete(self):
        for language in ("fa", "en"):
            self.assertEqual(len(localized(MODULES, language)), 19)
            self.assertEqual(len(localized(AGENT_SETTINGS, language)), 10)
            self.assertTrue(all(x["label"] for x in localized(MODULES, language)))

    def test_invalid_language_rejected(self):
        with self.assertRaises(ValueError):
            localized(MODULES, "de")
