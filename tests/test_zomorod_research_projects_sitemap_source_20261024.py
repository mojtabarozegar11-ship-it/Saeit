"""Offline regression for Zomorod public research register sitemap source.

Source-only test: live canonical, deployed route and Google indexing MUST be
verified separately before any production release.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = ROOT / "core" / "seo_views.py"
PROJECT_PATH = "/research/projects/"


class ResearchProjectsSitemapSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE_FILE.read_text(encoding="utf-8")
        module = ast.parse(cls.source, filename=str(SOURCE_FILE))
        cls.sitemap_function = next(
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == "sitemap_xml"
        )
        cls.literal_urls = next(
            ast.literal_eval(node.value)
            for node in cls.sitemap_function.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "urls" for t in node.targets)
            and isinstance(node.value, ast.List)
        )

    def test_public_project_register_in_static_sitemap_exactly_once(self):
        self.assertEqual(self.literal_urls.count(PROJECT_PATH), 1)
        self.assertIn("/research/", self.literal_urls)
        self.assertIn("/", self.literal_urls)

    def test_source_excludes_private_and_draft_research_routes(self):
        forbidden = ("admin", "api", "draft", "private", "stage-", "qa")
        for path in self.literal_urls:
            self.assertTrue(path.startswith("/") and path.endswith("/"))
            self.assertFalse(any(segment.startswith(forbidden)
                             for segment in path.strip("/").lower().split("/")))

    def test_sitemap_retains_xml_escape_and_deduplication(self):
        function_source = ast.get_source_segment(self.source, self.sitemap_function)
        self.assertIn("dict.fromkeys(urls)", function_source)
        self.assertIn("xml_escape(", function_source)
        self.assertIn('content_type="application/xml"', function_source)
        self.assertIn("filter(active=True)", function_source)
        self.assertIn("filter(published=True)", function_source)

    def test_no_source_only_test_can_claim_live_google_indexing(self):
        self.assertNotIn("google_indexed = True", self.source)
        self.assertNotIn("independent_qc_approved = True", self.source)


if __name__ == "__main__":
    unittest.main()
