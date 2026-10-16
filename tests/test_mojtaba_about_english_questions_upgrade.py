"""Regression tests for replacing ONLY the bilingual About FAQ with English."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "scripts/mojtaba_about_english_questions_upgrade.py"
SOURCE = ROOT / "content/mojtaba_personal_public_identity_faq_20261016.json"
SPEC = importlib.util.spec_from_file_location("personal_english_qa", PUBLISHER)
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)

class EnglishOnlyQuestionsTests(unittest.TestCase):
    def setUp(self):
        original = upgrade.base_module()
        self.old = original.block_markup(original.load_faq(SOURCE))
        self.rows = upgrade.english_rows(SOURCE)
        self.before = ('{% extends "personal_site/base.html" %}\n'
                       '{% block title %}Keep current SEO{% endblock %}\n'
                       '{% block content %}\n'
                       '<div id="owner-intro">' + "Keep owner biography and galleries. "*50
                       + "</div>\n")
        self.after = ('\n<div id="owner-gallery">Keep all owner photos</div>\n'
                      '{% endblock %}\n'
                      '{% block meta %}Keep original Person JSON-LD{% endblock %}\n')
        self.doc = self.before + self.old + self.after

    def test_one_english_faq_stays_inside_original_about(self):
        result = upgrade.patch(self.doc, self.rows)
        self.assertEqual(result.count(upgrade.FAQ_ID), 1)
        self.assertEqual(result.count(upgrade.UPGRADE_ID), 1)
        self.assertEqual(result.count(upgrade.FORM_ID), 1)
        self.assertTrue(result.startswith(self.before))
        self.assertTrue(result.endswith(self.after))
        section = upgrade.FAQ_SECTION.search(result).group()
        self.assertEqual(section.count("<article"), 8)
        self.assertFalse(upgrade.PERSIAN_CHARS.search(section))
        self.assertIn("Frequently Asked Questions", section)
        self.assertIn("Who is Mojtaba Roozegar?", section)
        self.assertNotIn('lang="fa"', section)
        self.assertIn("Keep original Person JSON-LD", result)

    def test_existing_csrf_contact_route_with_required_fields(self):
        section = upgrade.markup(self.rows)
        self.assertIn('method="post" action="/mojtaba.roozegar/contact/"', section)
        self.assertIn("{% csrf_token %}", section)
        for field in ("name", "email", "subject", "message", "website"):
            self.assertIn('name="' + field + '"', section)
        self.assertIn('type="email"', section)
        self.assertIn("required", section)
        self.assertIn("there is no automatic AI reply", section)

    def test_refuses_duplicate_upgrade(self):
        with self.assertRaisesRegex(ValueError, "Expected one original"):
            upgrade.patch(upgrade.patch(self.doc, self.rows), self.rows)

    def test_refuses_missing_old_faq(self):
        with self.assertRaisesRegex(ValueError, "Expected one original"):
            upgrade.patch(self.before + self.after, self.rows)

    def test_refuses_truncated_original_faq(self):
        broken = self.doc.replace('lang="fa"', 'lang="missing"', 1)
        with self.assertRaisesRegex(ValueError, "English and Persian groups"):
            upgrade.patch(broken, self.rows)

    def test_refuses_unsafe_project_folder(self):
        with self.assertRaises(ValueError):
            upgrade.base_module().safe_template(Path("/tmp/not-personal-site"))

    def test_source_never_displays_persian_qa(self):
        self.assertEqual(len(self.rows), 8)
        self.assertFalse(upgrade.PERSIAN_CHARS.search(upgrade.markup(self.rows)))

    def test_escapes_dynamic_question_and_answer(self):
        rows = list(self.rows)
        rows[0] = ("Who <script>?", "An answer <img src=x onerror=alert(1)>")
        block = upgrade.markup(rows)
        self.assertNotIn("<script>", block)
        self.assertNotIn("<img", block)
        self.assertIn("&lt;script&gt;", block)
        self.assertIn("&lt;img", block)

    def test_refuses_wrong_faq_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "faq.json"
            p.write_text('{"version":1,"target":"https://example.com","questions":[]}')
            with self.assertRaises(ValueError):
                upgrade.english_rows(p)

if __name__ == "__main__":
    unittest.main()
