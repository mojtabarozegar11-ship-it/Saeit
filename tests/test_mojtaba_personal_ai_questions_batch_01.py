"""Protect the old FAQ, visitor form, identity SEO and existing content."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/"scripts/mojtaba_personal_ai_questions_batch_01_publish.py"
DATA = ROOT/"content/mojtaba_personal_ai_questions_batch_01_20261016.json"
OLD_DATA = ROOT/"content/mojtaba_personal_public_identity_faq_20261016.json"
SPEC = importlib.util.spec_from_file_location("personal_ai_batch_01", PATH)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
OLD_SPEC = importlib.util.spec_from_file_location(
    "personal_english_upgrade", ROOT/"scripts/mojtaba_about_english_questions_upgrade.py")
old = importlib.util.module_from_spec(OLD_SPEC)
OLD_SPEC.loader.exec_module(old)

class Batch01Tests(unittest.TestCase):
    def setUp(self):
        self.rows = mod.read_batch(DATA)
        self.previous = old.markup(old.english_rows(OLD_DATA))
        self.prefix = ('{% extends "personal_site/base.html" %}'
                       '{% block content %}<h1>Public original biography</h1>'
                       '<div id="keep-existing-photos">Photos unchanged</div>')
        self.suffix = ('<div id="keep-existing-bio">Another biography section</div>'
                       '{% endblock %}{% block page_meta %}Person profile SEO unchanged'
                       '{% endblock %}')
        self.page = self.prefix + self.previous + self.suffix

    def test_exactly_ten_new_factual_questions(self):
        self.assertEqual([r["id"] for r in self.rows], list(range(9, 19)))
        q = [r["question"].lower() for r in self.rows]
        self.assertEqual(len(set(q)), 10)
        for row in self.rows:
            self.assertGreater(len(row["answer"]), 120)
            self.assertTrue(row["source_url"].startswith(mod.SITE))
            self.assertIsNone(mod.PERSIAN.search(row["question"]+row["answer"]))
        self.assertIn("self-reported", self.rows[0]["answer"].lower())
        self.assertIn("not evidence", self.rows[3]["answer"].lower())

    def test_ten_more_append_inside_about_only_and_preserve_existing_eight(self):
        updated = mod.patch(self.page, self.rows)
        self.assertTrue(updated.startswith(self.prefix))
        self.assertTrue(updated.endswith(self.suffix))
        sec = mod.SECTION.search(updated).group()
        self.assertEqual(sec.count("<article"), 18)
        self.assertEqual(sec.count('data-ai-faq-id="'), 10)
        self.assertEqual(sec.count(mod.NEW_ID), 1)
        self.assertIn(self.previous.split(mod.FORM_WRAPPER)[0], sec)
        self.assertIn(self.previous.split(mod.FORM_WRAPPER)[1], sec)
        self.assertEqual(sec.count(mod.FORM_ID), 1)
        self.assertEqual(sec.count("{% csrf_token %}"), 1)
        self.assertIsNone(mod.PERSIAN.search(sec))

    def test_readable_heading_and_verified_internal_sources(self):
        section = mod.render_batch(self.rows)
        self.assertIn("More Questions People May Ask AI Assistants", section)
        self.assertIn("not private queries or verified search trends", section)
        self.assertEqual(section.count("Read related source page"), 10)
        self.assertEqual(section.count("<article"), 10)
        self.assertNotIn('href="https://example.com', section)

    def test_refuses_duplicate(self):
        with self.assertRaisesRegex(ValueError, "already installed"):
            mod.patch(mod.patch(self.page, self.rows), self.rows)

    def test_refuses_changed_legacy_faq(self):
        damaged = self.page.replace(self.previous, self.previous.replace("<article", "<span", 1))
        with self.assertRaisesRegex(ValueError, "eight English answers"):
            mod.patch(damaged, self.rows)

    def test_refuses_missing_form(self):
        damaged = self.page.replace(mod.FORM_ID, 'id="other-form"')
        with self.assertRaisesRegex(ValueError, "markers"):
            mod.patch(damaged, self.rows)

    def test_refuses_source_outside_personal_website(self):
        import json
        data = json.loads(DATA.read_text(encoding="utf-8"))
        data["questions"][0]["source_url"] = "https://example.org/wrong"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"batch.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "existing personal"):
                mod.read_batch(path)

    def test_fails_closed_on_invalid_target(self):
        import json
        data = json.loads(DATA.read_text())
        data["target"] = "https://mojplaywin.com/"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"batch.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Wrong About"):
                mod.read_batch(path)

    def test_generated_markup_escapes_untrusted_text(self):
        rows = [dict(x) for x in self.rows]
        rows[0]["answer"] = 'Danger <img src=x onerror="x"> and "quoted" data'
        rendered = mod.render_batch(rows)
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)

    def test_private_and_public_site_independence(self):
        self.assertEqual(mod.ABOUT.as_posix(), "templates/personal_site/core/about.html")
        self.assertTrue(str(mod.APP).endswith("/mojtaba_roozegar_personal_v17"))
        self.assertEqual(mod.SITE, "https://mojplaywin.com/mojtaba.roozegar/")

if __name__=="__main__":
    unittest.main()
