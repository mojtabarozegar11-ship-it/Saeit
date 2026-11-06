"""Customer-extractable Python-only checks; never requires Node or source repo."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


class OfflineCustomerPackageTests(unittest.TestCase):
    def test_all_browser_assets_exist_without_external_files(self):
        for name in ("offline_calculator.html", "offline_engine.js", "offline_ui.js",
                     "calculator.py", "README.md", "example_inputs.json"):
            path = ROOT / name
            self.assertTrue(path.is_file(), name)
            self.assertFalse(path.is_symlink(), name)

    def test_offline_document_csp_and_local_scripts(self):
        page = (ROOT / 'offline_calculator.html').read_text(encoding='utf-8')
        self.assertIn("default-src 'none'", page)
        self.assertIn('aria-live="assertive"', page)
        self.assertIn('src="offline_engine.js"', page)
        self.assertIn('src="offline_ui.js"', page)
        self.assertNotIn('http://', page)
        self.assertNotIn('https://', page)


if __name__ == '__main__':
    unittest.main()
