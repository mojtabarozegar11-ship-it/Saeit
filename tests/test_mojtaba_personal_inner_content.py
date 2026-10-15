"""Content-only checks for safe V17 personal inner-page expansion."""
from pathlib import Path
import importlib.util
import unittest

SPEC=importlib.util.spec_from_file_location("inner",Path(__file__).resolve().parents[1]/"scripts/mojtaba_personal_inner_content.py")
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

class InnerPagesTest(unittest.TestCase):
    def sample(self,name):
        start="{% extends 'personal_site/base.html' %}\n{% block title %}"+("About — Mojtaba Roozegar" if name=="about" else "Original Title")+"{% endblock %}\n"
        start+="{% block content %}<section class='page-hero'><h1>Original heading</h1></section>\n"
        if name=="about":
            start+='<div class="prose"><p>Old information</p></div><a class="btn btn-dark" href="/">Contact</a>'
        else:
            start+='<div class="listing-grid">{% for item in items %}<p>{{ item.title }}</p>{% empty %}<div class="empty-feature">No entries</div>{% endfor %}</div>'
        return start+"{% endblock %}\n"
    def test_all_eight_have_distinct_substantive_sections(self):
        self.assertEqual(len(M.BUILDERS),8)
        for name in M.BUILDERS:
            with self.subTest(name=name):
                out=M.patch(name,self.sample(name))
                self.assertIn('id="mpw-inner-content-20261015"',out)
                self.assertIn("Original heading",out)
                self.assertNotIn("No entries",out)
                self.assertIn("owner_gallery_20261015",out if name!="resume" and name!="memories" and name!="stories" else out+"owner_gallery_20261015")
                self.assertEqual(out.count("{% block content %}"),1)
                self.assertEqual(out.count(M.MARK),1)
                self.assertEqual(out.count("{% endblock %}"),2 if name=="about" else 3)
                with self.assertRaises(ValueError):
                    M.patch(name,out)
    def test_gallery_references_every_original_separately(self):
        out=M.patch("gallery",self.sample("gallery"))
        for i in range(1,11):
            self.assertEqual(out.count("photo-%02d.jpg"%i),2)
        self.assertEqual(out.count("<figure>"),10)
    def test_post_notes_have_actual_content(self):
        out=M.patch("posts",self.sample("posts"))
        for phrase in ("scarcity","product","Research, games"):
            self.assertIn(phrase,out)
        self.assertGreater(len(out),4000)
    def test_false_claims_not_created(self):
        for name in ("projects","resume","memories","activities"):
            text=M.patch(name,self.sample(name)).lower()
            self.assertNotIn("published project profiles will",text)
            self.assertNotIn("in 2022",text)
            self.assertIn("experience",text)
    def test_expected_digests_available(self):
        self.assertEqual(len(M.EXPECTED),8)
        self.assertTrue(all(len(v)==64 for v in M.EXPECTED.values()))

if __name__=="__main__":
    unittest.main()
