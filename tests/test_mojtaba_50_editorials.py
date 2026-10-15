"""Regression tests: 50 truly separate articles, safe additive insertions, no fictitious factual claims."""
import importlib.util
import json
from pathlib import Path
import unittest

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("fifty",root/"scripts/mojtaba_50_editorials_safe_deploy.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
DATA=root/"content/mojtaba_personal_50_editorial_20261015.json"

def old_page():
    return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block title %}Original title{% endblock %}
{% block content %}
<div class="page"><h1>The original visible heading</h1>
<section id="mpw-new-originals-20261015-b"><p>Ten existing owner photos remain unchanged.</p></section>
<p id="important-user-content">Original biography and old content</p>
</div>
{% endblock %}
"""

class FiftyEditorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=mod.load_content(DATA)

    def test_exact_distribution_and_unique_titles(self):
        self.assertEqual(self.data["total"],50)
        counts={p:sum(x["page"]==p for x in self.data["entries"]) for p in mod.PAGE_FILES}
        self.assertEqual(counts,mod.COUNTS)
        self.assertEqual(sum(counts.values()),50)
        self.assertEqual(len({x["title"] for x in self.data["entries"]}),50)

    def test_all_entries_are_substantive(self):
        self.assertTrue(all(len((x["lead"]+" "+x["body"]).split())>=65 for x in self.data["entries"]))
        self.assertGreater(sum(len((x["lead"]+" "+x["body"]).split()) for x in self.data["entries"]),4000)

    def test_each_page_is_additive_preserves_old_pictures(self):
        for page in mod.PAGE_FILES:
            with self.subTest(page=page):
                original=old_page()
                new=mod.patch_template(page,original,self.data)
                self.assertIn("The original visible heading",new)
                self.assertIn("Original biography and old content",new)
                self.assertEqual(new.count(mod.MARKER),1)
                self.assertEqual(new.count(mod.PHOTO_MARKER),1)
                self.assertEqual(new.count("<article id=\"MPW-"),mod.COUNTS[page])
                self.assertEqual(new.count("{% block content %}"),1)
                self.assertEqual(new.count("{% endblock %}"),2)
                with self.assertRaises(ValueError):
                    mod.patch_template(page,new,self.data)

    def test_unrelated_page_or_removed_photo_panel_is_rejected(self):
        with self.assertRaises(ValueError):mod.patch_template("payments",old_page(),self.data)
        with self.assertRaises(ValueError):mod.patch_template("home",old_page().replace(mod.PHOTO_MARKER,"no-original-photos"),self.data)

    def test_stories_are_accurately_identified_as_fiction(self):
        stories=[x for x in self.data["entries"] if x["page"]=="stories"]
        self.assertEqual(len(stories),3)
        self.assertTrue(all(x["type"]=="Original fiction" for x in stories))
        body=mod.section("stories",self.data)
        self.assertIn("not verified personal events",body)

    def test_escaped_story_titles_are_valid_english_after_html_decode(self):
        from html import unescape
        story=next(x for x in self.data["entries"] if x["title"]=="A baker's ledger of impossible recipes")
        html_fragment=mod.section("stories",self.data)
        self.assertIn("&#x27;",html_fragment)
        self.assertIn(story["title"],unescape(html_fragment))

    def test_no_external_images_payments_or_scripts_added(self):
        for page in mod.PAGE_FILES:
            text=mod.section(page,self.data)
            for forbidden in ("<img","<script","bitcoin:","ethereum:","window.location","https://"):
                self.assertNotIn(forbidden,text)

    def test_journal_has_twelve_individual_targeted_links(self):
        out=mod.section("posts",self.data)
        self.assertEqual(out.count('<a href="#MPW-'),12)
        self.assertEqual(out.count("<article id=\"MPW-"),12)

if __name__=="__main__":
    unittest.main()
