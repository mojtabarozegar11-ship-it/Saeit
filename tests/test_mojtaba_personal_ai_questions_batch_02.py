"""Regression checks for approved English batch 02: append only within personal About."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/"scripts"

def load(path, name):
    spec=importlib.util.spec_from_file_location(name, path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

batch2=load(SCRIPTS/"mojtaba_personal_ai_questions_batch_02_publish.py","personal_faq_batch2")
batch1=load(SCRIPTS/"mojtaba_personal_ai_questions_batch_01_publish.py","personal_faq_batch1")
initial=load(SCRIPTS/"mojtaba_about_english_questions_upgrade.py","personal_english_initial")
SRC=ROOT/"content/mojtaba_personal_ai_questions_batch_02_20261016.json"
SRC1=ROOT/"content/mojtaba_personal_ai_questions_batch_01_20261016.json"
ORIGINAL=ROOT/"content/mojtaba_personal_public_identity_faq_20261016.json"

class UserApprovedBatchTwoTests(unittest.TestCase):
    def setUp(self):
        self.rows=batch2.read_batch(SRC)
        self.prefix=(
            '{% extends "personal_site/base.html" %}\n'
            '{% block title %}Existing optimized About title{% endblock %}\n'
            '{% block content %}\n'
            '<section id="original-biography">Keep every paragraph and photo</section>\n'
        )
        self.suffix=(
            '<section id="existing-about-footer">Keep all old sections</section>\n'
            '{% endblock %}\n'
            '{% block meta %}Original Person and canonical SEO stays{% endblock %}\n'
        )
        base=initial.markup(initial.english_rows(ORIGINAL))
        self.before=batch1.patch(self.prefix+base+self.suffix,batch1.read_batch(SRC1))

    def test_exactly_ten_user_approved_ids_and_english_answers(self):
        self.assertEqual([q["id"] for q in self.rows],list(range(19,29)))
        self.assertEqual(len({q["question"].casefold() for q in self.rows}),10)
        for item in self.rows:
            self.assertGreaterEqual(len(item["answer"]),130)
            self.assertNotRegex(item["question"]+item["answer"],r"[\u0600-\u06FF]")
        self.assertIn("human",self.rows[5]["answer"])
        self.assertIn("scientific accuracy",self.rows[7]["answer"])
        self.assertIn("independent validation",self.rows[1]["answer"])

    def test_full_preservation_and_scope_to_about(self):
        after=batch2.patch(self.before,self.rows)
        self.assertTrue(after.startswith(self.prefix))
        self.assertTrue(after.endswith(self.suffix))
        original_section=batch2.SECTION.search(self.before).group()
        new_section=batch2.SECTION.search(after).group()
        self.assertEqual(original_section.count("<article"),18)
        self.assertEqual(new_section.count("<article"),28)
        self.assertEqual(new_section.count('data-ai-faq-id="'),20)
        self.assertEqual(new_section.count(batch2.FORM_ID),1)
        self.assertEqual(new_section.count("{% csrf_token %}"),1)
        self.assertEqual(new_section.count(batch2.FIRST_BATCH_ID),1)
        self.assertEqual(new_section.count(batch2.SECOND_BATCH_ID),1)
        self.assertEqual(new_section.count('data-ai-faq-id="19"'),1)
        self.assertEqual(new_section.count('data-ai-faq-id="28"'),1)
        self.assertNotRegex(new_section,r"[\u0600-\u06FF]")
        # The previous entire FAQ HTML stays byte-for-byte: only a new block
        # is inserted immediately before the original contact form.
        old_left,old_right=original_section.split(batch2.FORM_WRAPPER,1)
        new_left,new_right=new_section.split(batch2.FORM_WRAPPER,1)
        self.assertTrue(new_left.startswith(old_left))
        self.assertEqual(new_right,old_right)

    def test_duplicate_install_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"already present"):
            batch2.patch(batch2.patch(self.before,self.rows),self.rows)

    def test_changes_to_prior_answers_block_publication(self):
        damaged=self.before.replace('data-ai-faq-id="9"','data-ai-faq-id="99"')
        with self.assertRaisesRegex(ValueError,"Prior question missing"):
            batch2.patch(damaged,self.rows)

    def test_removed_existing_form_blocks_publication(self):
        damaged=self.before.replace(batch2.FORM_ID,'id="broken-existing-form"')
        with self.assertRaisesRegex(ValueError,"previous eighteen"):
            batch2.patch(damaged,self.rows)

    def test_bad_destination_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad.json"
            data=json.loads(SRC.read_text())
            data["target"]="https://mojplaywin.com/about/"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Wrong batch or target"):
                batch2.read_batch(path)

    def test_unapproved_batch_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad.json"
            data=json.loads(SRC.read_text())
            data["approval"]="pending"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"explicit approval"):
                batch2.read_batch(path)

    def test_external_source_and_persian_text_are_refused(self):
        for edit in ("source","persian"):
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as d:
                path=Path(d)/"bad.json"
                data=json.loads(SRC.read_text())
                if edit=="source":
                    data["questions"][0]["source_url"]="https://unrelated.example/"
                else:
                    data["questions"][0]["answer"]+=" فارسی"
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    batch2.read_batch(path)

    def test_safe_render_escapes_html(self):
        rows=[dict(q) for q in self.rows]
        rows[0]["question"]='Question <img src=x onerror=alert(1)>?'
        rendered=batch2.render_batch(rows)
        self.assertNotIn("<img",rendered)
        self.assertIn("&lt;img",rendered)

    def test_existing_93_articles_and_images_guards_reused(self):
        guard=batch2.guard_module()
        self.assertEqual(str(guard.REL),"templates/personal_site/core/about.html")
        self.assertEqual(guard.APP,batch2.APP)
        self.assertEqual(batch2.SITE,"https://mojplaywin.com/mojtaba.roozegar/")
        self.assertEqual(len(self.rows),10)

if __name__=="__main__":
    unittest.main()
