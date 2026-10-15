import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/mojtaba_personal_expanded_library_deploy.py"
DATA = ROOT / "content/mojtaba_personal_expanded_library_20261016.json"
spec = importlib.util.spec_from_file_location("expanded", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def sample():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<section id="mpw-fifty-editorials-20261015">50 prior editorials</section>
<section id="mpw-new-originals-20261015-b">20 owner photographs</section>
<section id="mpw-academic-profile-20261016">Previous academic biography</section>
<p>Existing history and content must remain.</p>
{% endblock %}"""

class PersonalExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = mod.read_content(DATA)

    def test_exactly_five_allowlisted_pages_with_complete_sections(self):
        self.assertEqual(set(self.data["pages"]), set(mod.PAGES))
        self.assertGreaterEqual(sum(len(p["sections"]) for p in self.data["pages"].values()), 30)

    def test_preserve_prior_biography_articles_photos_and_html(self):
        for page in mod.PAGES:
            with self.subTest(page=page):
                out = mod.patch(page, sample(), self.data)
                self.assertIn("Existing history and content must remain", out)
                for marker in (mod.MARKER, mod.OLD_ACADEMIC, mod.OLD_EDITORIAL, mod.OLD_PHOTOS):
                    self.assertEqual(out.count(marker), 1)
                self.assertIn("</article>", out)
                self.assertIn("About", out)
                self.assertIn("Journal", out)
                with self.assertRaises(ValueError):
                    mod.patch(page, out, self.data)

    def test_section_prose_is_substantial_unique_and_escaped(self):
        count = 0
        titles = set()
        for page in mod.PAGES:
            for section in self.data["pages"][page]["sections"]:
                self.assertNotIn(section["title"], titles)
                titles.add(section["title"])
                self.assertEqual(len(section["paragraphs"]), 2)
                count += sum(len(s.split()) for s in section["paragraphs"])
            html_section = mod.render_section(page, self.data)
            self.assertIn("mpw-personal-expanded-20261016", html_section)
            self.assertNotIn("<script", html_section)
        self.assertGreaterEqual(count, 2500)

    def test_unrelated_page_rejected_and_missing_protection_refused(self):
        with self.assertRaises(ValueError):
            mod.patch("gallery", sample(), self.data)
        for marker in (mod.OLD_EDITORIAL, mod.OLD_PHOTOS, mod.OLD_ACADEMIC):
            with self.assertRaises(ValueError):
                mod.patch("home", sample().replace(marker, "missing"), self.data)

    def test_safe_rollback_restores_original_five_templates(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "app"
            template_dir = root / "templates/personal_site/core"
            template_dir.mkdir(parents=True)
            (root / "manage.py").write_text("# test", encoding="utf-8")
            backup = pathlib.Path(d) / "backups"
            backup.mkdir()
            for name in mod.PAGES.values():
                (template_dir / name).write_text("modified", encoding="utf-8")
                (backup / name).write_text(sample(), encoding="utf-8")
            mod.rollback(root, backup)
            for name in mod.PAGES.values():
                self.assertEqual((template_dir / name).read_text(), sample())

if __name__ == "__main__":
    unittest.main()
