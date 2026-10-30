"""One-entry-only author sitemap recency tests."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "author_sitemap",
    Path(__file__).resolve().parents[1] / "scripts/zomorod_author_sitemap_recency_20261030.py",
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
EXAMPLE = (
    b'<?xml version="1.0" encoding="utf-8"?>'
    b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    b'<url><loc>https://zomorodmelal.ir/</loc><lastmod>2026-09-01</lastmod></url>'
    + mod.OLD
    + b'<url><loc>https://zomorodmelal.ir/en/</loc></url></urlset>'
)


class AuthorSitemapRecencyTests(unittest.TestCase):
    def test_only_one_author_timestamp_changes(self):
        result = mod.transform(EXAMPLE)
        self.assertEqual(result.count(mod.NEW), 1)
        self.assertEqual(result.count(mod.OLD), 0)
        self.assertEqual(result.replace(mod.NEW, mod.OLD), EXAMPLE)
        self.assertIn(b"2026-09-01", result)
        with self.assertRaises(ValueError):
            mod.transform(result)

    def test_fail_closed_on_missing_duplicate_or_other_sitemap(self):
        for invalid in (
            EXAMPLE.replace(mod.OLD, b""),
            EXAMPLE.replace(mod.OLD, mod.OLD + mod.OLD),
            b"<html><body>Not a sitemap</body></html>",
        ):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(ValueError):
                    mod.transform(invalid)

    def test_fixed_narrow_path(self):
        self.assertEqual(str(mod.TARGET), "/home/zomorod2/public_html/sitemap.xml")
        self.assertNotIn("..", str(mod.BACKUP_ROOT))
        self.assertEqual(mod.URL, "https://zomorodmelal.ir/authors/mojtaba-rozegar/")


if __name__ == "__main__":
    unittest.main()
