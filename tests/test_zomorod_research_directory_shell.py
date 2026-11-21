"""Regression checks for the V7 research-directory page shell (60 pages)."""
from html.parser import HTMLParser
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest


GENERATOR = (
    Path(__file__).resolve().parents[1]
    / "content"
    / "zomorod-three-research-shelves"
    / "zomorod_three_shelves.py"
)


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        self.names.append(tag)


class ResearchDirectoryShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = spec_from_file_location("research_directory", GENERATOR)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.generator = module

    def test_all_sixty_pages_use_v7_shell_without_duplicate_header_footer(self):
        checked = 0
        for _, group_title, group, _, raw in self.generator.GROUPS:
            for title, slug, subject in self.generator.items(raw):
                html = self.generator.page_html(group, group_title, title, slug, subject)
                tags = _Tags()
                tags.feed(html)
                self.assertEqual(tags.names.count("header"), 0)
                self.assertEqual(tags.names.count("footer"), 0)
                self.assertEqual(tags.names.count("main"), 1)
                self.assertEqual(tags.names.count("nav"), 1)
                self.assertEqual(tags.names.count("h1"), 1)
                self.assertIn('aria-label="مسیر دسترسی"', html)
                self.assertIn('href="/research/"', html)
                self.assertIn('href="/company/"', html)
                self.assertIn(f"/research/directory/{group}/{slug}/", html)
                self.assertIn("به‌تنهایی به معنای وجود آزمایشگاه مستقل", html)
                checked += 1
        self.assertEqual(checked, 60)


if __name__ == "__main__":
    unittest.main()
