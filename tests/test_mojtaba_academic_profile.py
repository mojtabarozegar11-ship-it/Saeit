import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/"scripts/mojtaba_academic_profile_safe_deploy.py"
DATA=ROOT/"content/mojtaba_education_and_professional_bio_20261016.json"
spec=importlib.util.spec_from_file_location("academic",SRC)
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

def template():
    return """{% extends 'personal_site/base.html' %}
{% load static %}
{% block title %}Existing title{% endblock %}
{% block content %}
<div id="mpw-new-originals-20261015-b">Owner's existing original photos</div>
<div id="mpw-fifty-editorials-20261015">Fifty existing editorial articles</div>
<p>Existing personal biography must remain.</p>
{% endblock %}
"""

class EducationProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=app.read_content(DATA)

    def test_exact_five_pages(self):
        self.assertEqual(set(self.source["pages"]),set(app.PAGES))
        self.assertEqual(len(app.PAGES),5)

    def test_academic_identity(self):
        identity=self.source["identity"]
        self.assertEqual(identity["degree"],"PhD in Agricultural Economics")
        self.assertEqual(identity["university"],"Universiti Putra Malaysia (UPM)")
        self.assertEqual(identity["specialization"],"Production Economics and Farm Management")

    def test_additive_five_pages_preserve_all_prior_sections(self):
        for page in app.PAGES:
            with self.subTest(page=page):
                out=app.patch(page,template(),self.source)
                self.assertIn("Existing personal biography must remain",out)
                self.assertEqual(out.count(app.MARKER),1)
                self.assertEqual(out.count(app.PREVIOUS_EDITORIAL),1)
                self.assertEqual(out.count(app.PREVIOUS_PHOTOS),1)
                self.assertIn("{% block content %}",out)
                self.assertEqual(out.count("{% endblock %}"),2)
                with self.assertRaises(ValueError):
                    app.patch(page,out,self.source)

    def test_multiple_educational_paragraphs_no_unsupported_year(self):
        for page in app.PAGES:
            with self.subTest(page=page):
                section=app.render_section(page,self.source)
                self.assertIn("PhD",section)
                self.assertIn("Agricultural Economics",section)
                self.assertTrue("2021" not in section and "2022" not in section)
                self.assertNotIn("<script",section)

    def test_no_change_to_unrelated_templates(self):
        for bad in ["gallery","memories","stories","payments"]:
            with self.assertRaises(ValueError):
                app.patch(bad,template(),self.source)

    def test_reject_when_existing_50_articles_or_photos_are_missing(self):
        with self.assertRaises(ValueError):
            app.patch("home",template().replace(app.PREVIOUS_EDITORIAL,"deleted"),self.source)
        with self.assertRaises(ValueError):
            app.patch("home",template().replace(app.PREVIOUS_PHOTOS,"deleted"),self.source)

    def test_owner_academic_and_honest_disclosure(self):
        for page in app.PAGES:
            record=self.source["pages"][page]
            self.assertTrue(record["note"])
            self.assertTrue(len(record["facts"])>=3)
        self.assertIn("verified",self.source["pages"]["resume"]["note"].lower())
        self.assertIn("educational",self.source["pages"]["posts"]["note"].lower())

if __name__=="__main__":
    unittest.main()
