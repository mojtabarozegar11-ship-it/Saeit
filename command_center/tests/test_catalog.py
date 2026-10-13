import unittest
from command_center.catalog import MODULES, AGENT_SETTINGS, localized


class CatalogTests(unittest.TestCase):
    def test_module_ids_unique(self):
        self.assertEqual(len({m[0] for m in MODULES}), len(MODULES))

    def test_both_languages_complete(self):
        for language in ("fa", "en"):
            self.assertEqual(len(localized(MODULES, language, admin_links=True)), 19)
            self.assertEqual(len(localized(AGENT_SETTINGS, language)), 10)
            self.assertFalse(any(x["connected"] for x in localized(AGENT_SETTINGS, language)))
            self.assertTrue(all(x["label"] for x in localized(MODULES, language)))

    def test_only_real_admin_surfaces_are_marked_connected(self):
        modules = {item["id"]: item for item in localized(MODULES, "fa", admin_links=True)}
        self.assertTrue(modules["agents"]["connected"])
        self.assertEqual(modules["agents"]["route_name"], "admin:core_agent_changelist")
        self.assertFalse(modules["infrastructure"]["connected"])
        self.assertEqual(modules["infrastructure"]["route_name"], "")

    def test_invalid_language_rejected(self):
        with self.assertRaises(ValueError):
            localized(MODULES, "de")
