"""Personal SEO unit tests: single Person identity, verified aliases and transparent scholarship."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mr_seo", ROOT / "scripts/mojtaba_identity_seo_20261027.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def base_source():
    graph = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "@id": "https://mojplaywin.com/mojtaba.roozegar/#webpage",
        "mainEntity": {
            "@type": "Person",
            "@id": "https://mojplaywin.com/mojtaba.roozegar/#person",
            "name": "Mojtaba Roozegar",
            "alternateName": [
                "مجتبی روزگار", "روزگار", "Roozegar", "Mojtaba Roozegar",
                "Mojtaba Rozegar", "Rozegar", "Dr. Mojtaba Roozegar",
                "Dr.mojtaba.rozegar",
            ],
            "jobTitle": ["Entrepreneur", "Business Executive", "Researcher"],
            "sameAs": ["https://zomorodmelal.ir/authors/mojtaba-rozegar/"],
        },
    }
    return '<html><script type="application/ld+json">' + json.dumps(
        graph, ensure_ascii=False, separators=(",", ":")
    ) + '</script><h1>Existing site</h1></html>'


def about_source():
    return """
{% extends 'personal_site/base.html' %}
{% block description %}Mojtaba Roozegar is a founder.{% endblock %}
{% block content %}
<p>I am Mojtaba Roozegar, also written مجتبی روزگار in Persian.</p>
<div>Vancouver, British Columbia, Canada</div>
<div>Universiti Putra Malaysia (UPM)</div>
<p>I have described my scientific work as researcher and author, including the development of specialized books, educational materials and encyclopedic projects. These are areas of work and research interest; a specific publication or credential should only be described as completed when its details are individually documented.</p>
{% endblock %}
"""


def home_source():
    return """
{% extends 'personal_site/base.html' %}
{% block description %}Official website of Mojtaba Roozegar (مجتبی روزگار), entrepreneur, business executive and researcher. Explore his work, ideas and writing.{% endblock %}
{% block og_description %}Mojtaba Roozegar is an entrepreneur, business executive and researcher. Read about his work, ideas and writing.{% endblock %}
{% block content %}
<p>Mojtaba Roozegar is an entrepreneur, business executive and researcher. This independent website brings together his work, ideas and writing.</p>
{% endblock %}
"""


class PersonSEOTests(unittest.TestCase):
    def test_adds_only_missing_transliterations_to_existing_person(self):
        original = base_source()
        updated = mod.revise_shared_meta(original)
        self.assertEqual(updated.count('type="application/ld+json"'), 1)
        json_raw = re.search(r'<script type="application/ld\+json">(.*?)</script>', updated).group(1)
        node = json.loads(json_raw)
        person = node["mainEntity"]
        self.assertEqual(person["@id"], "https://mojplaywin.com/mojtaba.roozegar/#person")
        self.assertTrue(all(alias in person["alternateName"] for alias in mod.ALIAS_REQUIRED))
        self.assertEqual(len(person["alternateName"]), len(set(person["alternateName"])))
        self.assertIn("Author", person["jobTitle"])
        self.assertIn("Universiti Putra Malaysia", person["alumniOf"]["name"])
        self.assertIn("Vancouver", person["homeLocation"]["name"])
        self.assertEqual(person["sameAs"], [
            "https://zomorodmelal.ir/authors/mojtaba-rozegar/"])
        with self.assertRaises(ValueError):
            mod.revise_shared_meta(updated)

    def test_home_meta_and_hero_are_natural(self):
        updated = mod.revise_home(home_source())
        self.assertIn("مجتبی روزگار", updated)
        self.assertIn("scientific author", updated)
        self.assertIn("Vancouver", updated)
        self.assertEqual(updated.count("{% block description %}"), 1)
        self.assertEqual(updated.count("{% block og_description %}"), 1)
        with self.assertRaises(ValueError):
            mod.revise_home(updated)

    def test_about_content_is_precise_and_no_false_publication_claim(self):
        updated = mod.revise_about(about_source())
        self.assertIn("Mojtaba Rouzegar", updated)
        self.assertIn("Mojtaba Rozegar", updated)
        self.assertIn("مجتبی روزگار", updated)
        self.assertIn("several scientific articles", updated)
        self.assertIn("journal-reviewed publications", updated)
        self.assertNotIn("multiple published peer-reviewed", updated)
        with self.assertRaises(ValueError):
            mod.revise_about(updated)

    def test_fail_closed_on_scope_and_malformed_person(self):
        self.assertEqual(mod.RELATIVES, (
            "templates/personal_site/base.html",
            "templates/personal_site/core/home.html",
            "templates/personal_site/core/about.html",
        ))
        self.assertNotIn("public_html", str(mod.APP))
        with self.assertRaises(ValueError):
            mod.revise_shared_meta('<script type="application/ld+json">{"@type":"Organization"}</script>')
        with self.assertRaises(ValueError):
            mod.revise_shared_meta("missing script")


if __name__ == "__main__":
    unittest.main()
