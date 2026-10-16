"""Regression tests for additive, private-backup personal FAQ publication."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "faq_safe", ROOT / "scripts/mojtaba_personal_public_faq_safe_publish.py"
)
faq = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(faq)
DATA = ROOT / "content/mojtaba_personal_public_identity_faq_20261016.json"

class FAQTests(unittest.TestCase):
    def setUp(self):
        self.rows = faq.load_faq(DATA)
        self.html = (
            '{% extends "personal_site/base.html" %}\n'
            '{% block title %}Original title{% endblock %}\n'
            '{% block content %}\n'
            '<section id="keep-original">Original public biography.</section>\n'
            '{% endblock %}\n'
            '{% block extra_head %}Original structured data{% endblock %}\n'
        )

    def test_only_about_content_block_is_extended(self):
        updated = faq.patch(self.html, self.rows)
        self.assertEqual(updated.count(faq.MARK), 1)
        self.assertIn('id="keep-original"', updated)
        self.assertIn("Original structured data", updated)
        self.assertTrue(updated.endswith('{% endblock %}\n'))
        self.assertIn("پرسش‌های متداول", updated)
        self.assertIn("Who is Mojtaba Roozegar?", updated)
        self.assertEqual(updated.count("<article "), 16)

    def test_refuses_duplicate(self):
        with self.assertRaisesRegex(ValueError, "already installed"):
            faq.patch(faq.patch(self.html, self.rows), self.rows)

    def test_refuses_missing_content_block(self):
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            faq.patch("<html><body>not a template</body></html>", self.rows)

    def test_nested_blocks_do_not_break_insertion(self):
        source = (
            "{% block content %}A{% block inner %}B{% endblock %}C"
            "{% endblock %}{% block footer %}Keep{% endblock %}"
        )
        out = faq.patch(source, self.rows)
        self.assertLess(out.index(faq.MARK), out.index("{% block footer %}"))
        self.assertIn("{% block footer %}Keep{% endblock %}", out)

    def test_all_public_answers_escaped(self):
        for row in self.rows:
            for lang in ("en", "fa"):
                self.assertTrue(row[lang]["question"] in faq.block_markup(self.rows))
        custom = [{**row, "en": dict(row["en"])} for row in self.rows]
        custom[0]["en"]["question"] = "Question <script>alert('hello')</script>"
        markup = faq.block_markup(custom)
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_safe_scoped_json_validation(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "faq.json"
            bad.write_text('{"version":1,"target":"https://example.com","questions":[]}')
            with self.assertRaisesRegex(ValueError, "Wrong personal FAQ scope"):
                faq.load_faq(bad)

    def test_strict_application_scope(self):
        with self.assertRaises(ValueError):
            faq.safe_template(Path("/tmp/other-project"))

if __name__ == "__main__":
    unittest.main()
