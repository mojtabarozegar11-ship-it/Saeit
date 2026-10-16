import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/mojtaba_seven_native_articles_publish.py"
DOC = ROOT / "content/mojtaba_seven_full_independent_journal_20261016.json"
spec = importlib.util.spec_from_file_location("journal", SRC)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def old_template():
    return """{% extends 'personal_site/base.html' %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Original photos</div>
<div id="mpw-fifty-editorials-20261015">Original fifty articles</div>
<div id="mpw-academic-profile-20261016">Academic biography</div>
<div id="mpw-personal-expanded-20261016">Previous 32 sections</div>
<p>Historical content must remain.</p>
{% endblock %}"""

class NativeJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=m.load_manifest(DOC)

    def test_seven_full_length_articles_and_unique_slug(self):
        rows=self.data["articles"]
        self.assertEqual(len(rows),7)
        self.assertEqual(len(set(x["slug"] for x in rows)),7)
        self.assertEqual(len(set(x["title"] for x in rows)),7)
        self.assertTrue(all(len(x["content"].split())>=400 for x in rows))
        self.assertGreater(sum(len(x["content"].split()) for x in rows),3000)

    def test_native_articles_index_has_correct_links(self):
        html=m.index_block(self.data)
        for x in self.data["articles"]:
            self.assertIn("/mojtaba.roozegar/blog/"+x["slug"]+"/",html)
            self.assertIn(x["title"],html)
        self.assertEqual(html.count("href="),7)
        self.assertIn("mpw-journal-longform-index-20261016",html)

    def test_additive_preserves_prior_material_on_both_pages(self):
        for name in m.TEMPLATES:
            with self.subTest(page=name):
                original=old_template()
                patched=m.patch_template(original,self.data)
                self.assertIn("Historical content must remain",patched)
                for token in m.PROTECTED:
                    self.assertEqual(patched.count(token),1)
                self.assertEqual(patched.count(m.MARKER),1)
                with self.assertRaises(ValueError):
                    m.patch_template(patched,self.data)

    def test_missing_prior_sections_fails_closed(self):
        for token in m.PROTECTED:
            with self.subTest(marker=token):
                with self.assertRaises(ValueError):
                    m.patch_template(old_template().replace(token,"deleted"),self.data)

    def test_reject_duplicate_or_insubstantial_articles(self):
        with tempfile.TemporaryDirectory() as temp:
            data=json.loads(DOC.read_text())
            data["articles"][1]["slug"]=data["articles"][0]["slug"]
            out=Path(temp)/"test.json"
            out.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):m.load_manifest(out)
            data["articles"][1]["slug"]="unique-valid-slug-fresh"
            data["articles"][1]["content"]="Too short"
            out.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):m.load_manifest(out)

    def test_check_app_and_allowlist(self):
        self.assertEqual(set(m.TEMPLATES),{"home","posts"})
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                m.read_templates(Path(temp))

if __name__=="__main__":
    unittest.main()
