"""Approved batch-three FAQ regression: exactly 28 old items retained, ten new."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CONTENT = ROOT / "content"

def load(filename, name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

batch3 = load("mojtaba_personal_ai_questions_batch_03_publish.py", "personal_batch3")
batch2 = load("mojtaba_personal_ai_questions_batch_02_publish.py", "personal_batch2")
batch1 = load("mojtaba_personal_ai_questions_batch_01_publish.py", "personal_batch1")
initial = load("mojtaba_about_english_questions_upgrade.py", "personal_english_baseline")
SOURCE = CONTENT / "mojtaba_personal_ai_questions_batch_03_20261016.json"

class ApprovedBatch3Tests(unittest.TestCase):
    def setUp(self):
        self.rows = batch3.read_batch(SOURCE)
        self.prefix = (
            '{% extends "personal_site/base.html" %}\n'
            '{% block title %}Preserve original About title{% endblock %}\n'
            '{% block content %}\n'
            '<div id="public-biography">All existing biography and pictures</div>\n'
        )
        self.suffix = (
            '<div id="existing-photos">Protected photos and timeline</div>\n'
            '{% endblock %}\n'
            '{% block meta %}Existing Person JSON-LD and canonical{% endblock %}\n'
        )
        base = initial.markup(initial.english_rows(
            CONTENT / "mojtaba_personal_public_identity_faq_20261016.json"))
        after1 = batch1.patch(self.prefix + base + self.suffix, batch1.read_batch(
            CONTENT / "mojtaba_personal_ai_questions_batch_01_20261016.json"))
        self.before = batch2.patch(after1, batch2.read_batch(
            CONTENT / "mojtaba_personal_ai_questions_batch_02_20261016.json"))

    def test_exactly_ten_approved_english_questions_and_sources(self):
        self.assertEqual([r["id"] for r in self.rows], list(range(29, 39)))
        self.assertEqual(len({r["question"].casefold() for r in self.rows}), 10)
        self.assertEqual(len({r["topic"] for r in self.rows}), 10)
        for entry in self.rows:
            self.assertGreaterEqual(len(entry["answer"]), 130)
            self.assertTrue(entry["source_url"].startswith(batch3.SITE))
            self.assertNotRegex(entry["question"]+entry["answer"], r"[\u0600-\u06FF]")
        self.assertIn("independent", self.rows[2]["answer"])
        self.assertIn("authorization", self.rows[3]["answer"])
        self.assertIn("independ", self.rows[9]["answer"])

    def test_appends_without_changing_a_single_existing_byte(self):
        after = batch3.patch(self.before, self.rows)
        self.assertTrue(after.startswith(self.prefix))
        self.assertTrue(after.endswith(self.suffix))
        old = batch3.SECTION.search(self.before).group()
        new = batch3.SECTION.search(after).group()
        self.assertEqual(old.count("<article"), 28)
        self.assertEqual(new.count("<article"), 38)
        self.assertEqual(old.count('data-ai-faq-id="'), 20)
        self.assertEqual(new.count('data-ai-faq-id="'), 30)
        left_old, right_old = old.split(batch3.FORM_WRAPPER, 1)
        left_new, right_new = new.split(batch3.FORM_WRAPPER, 1)
        self.assertTrue(left_new.startswith(left_old))
        self.assertEqual(right_new, right_old)
        self.assertEqual(new.count("{% csrf_token %}"), 1)
        for name in (batch3.FIRST_BATCH_ID, batch3.SECOND_BATCH_ID,
                     batch3.THIRD_BATCH_ID, batch3.FORM_ID):
            self.assertEqual(new.count(name), 1)
        self.assertNotRegex(new, r"[\u0600-\u06FF]")

    def test_every_previous_question_id_and_new_id_preserved(self):
        after = batch3.patch(self.before, self.rows)
        for number in range(9, 39):
            self.assertEqual(after.count('data-ai-faq-id="' + str(number) + '"'), 1)

    def test_refuses_a_duplicate_third_batch(self):
        once = batch3.patch(self.before, self.rows)
        with self.assertRaisesRegex(ValueError, "already present"):
            batch3.patch(once, self.rows)

    def test_previous_batch_one_must_exist(self):
        changed = self.before.replace(batch3.FIRST_BATCH_ID, 'id="broken-first-batch"')
        with self.assertRaisesRegex(ValueError, "Previous twenty-eight"):
            batch3.patch(changed, self.rows)

    def test_previous_batch_two_must_exist(self):
        changed = self.before.replace(batch3.SECOND_BATCH_ID, 'id="broken-second-batch"')
        with self.assertRaisesRegex(ValueError, "Previous twenty-eight"):
            batch3.patch(changed, self.rows)

    def test_missing_form_or_csrf_refuses_installation(self):
        for before, after in ((batch3.FORM_ID, 'id="missing-form"'),
                              ("{% csrf_token %}", "{% removed_token %}")):
            with self.subTest(before=before):
                damaged = self.before.replace(before, after, 1)
                with self.assertRaises(ValueError):
                    batch3.patch(damaged, self.rows)

    def test_changed_old_question_id_refuses_installation(self):
        damaged = self.before.replace('data-ai-faq-id="19"', 'data-ai-faq-id="99"')
        with self.assertRaisesRegex(ValueError, "Prior question missing"):
            batch3.patch(damaged, self.rows)

    def test_unapproved_content_refuses_publication(self):
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
        data["approval"] = "pending"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "no_approval.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "explicit approval"):
                batch3.read_batch(path)

    def test_wrong_domain_and_persian_content_refused(self):
        for kind in ("target", "external_source", "persian_answer"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                data = json.loads(SOURCE.read_text(encoding="utf-8"))
                if kind == "target":
                    data["target"] = "https://mojplaywin.com/about/"
                elif kind == "external_source":
                    data["questions"][0]["source_url"] = "https://example.org/"
                else:
                    data["questions"][0]["answer"] += " فارسی"
                path = Path(folder) / "invalid.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    batch3.read_batch(path)

    def test_rendering_escapes_dynamic_html(self):
        rows = [dict(row) for row in self.rows]
        rows[0]["answer"] = 'Unsafe <img src=x onerror=alert(1)> and "quotes"'
        markup = batch3.render_batch(rows)
        self.assertNotIn("<img", markup)
        self.assertIn("&lt;img", markup)

    def test_guard_still_targets_only_independent_personal_about(self):
        guard = batch3.guard_module()
        self.assertEqual(str(guard.REL), "templates/personal_site/core/about.html")
        self.assertEqual(batch3.APP, guard.APP)
        self.assertEqual(batch3.ABOUT.as_posix(), "templates/personal_site/core/about.html")
        self.assertEqual(batch3.SITE, "https://mojplaywin.com/mojtaba.roozegar/")

if __name__ == "__main__":
    unittest.main()
