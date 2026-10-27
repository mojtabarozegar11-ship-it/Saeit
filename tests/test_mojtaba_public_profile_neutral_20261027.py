"""Guarded public-claim editing tests; never invent current residence."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mr_profile_neutral", ROOT / "scripts/mojtaba_public_profile_neutral_20261027.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def about_source():
    return """
{% extends "personal_site/base.html" %}
{% block description %}Mojtaba Roozegar is an entrepreneur, business executive, researcher and lecturer based in Vancouver, Canada.{% endblock %}
{% block content %}
<h1>About Me.</h1>
<p>I am a researcher from Iran, now based in Vancouver, British Columbia, Canada.</p>
<p>My move to Canada was unexpected and not part of my original plans.</p>
<p>a new professional beginning in Vancouver</p>
<p>VANCOUVER, BC</p>
<p>into a new chapter abroad</p>
<p>An unexpected move has changed my circumstances, not the value of what I have learned.</p>
<p>This site welcomes people in Canada and internationally.</p>
<p>My unexpected relocation to Vancouver made continuity especially important: evidence remains primary.</p>
<section id="mpw-academic-profile-20261016">Owner-reported doctorate</section>
{% endblock %}
"""


class PublicClaimsTests(unittest.TestCase):
    def test_about_neutral_does_not_invent_new_location(self):
        after = mod.revise_about(about_source())
        self.assertNotIn("Vancouver", after)
        self.assertNotIn("Canada", after)
        self.assertNotIn("lecturer", after)
        self.assertIn("academic", after)
        self.assertIn("research and professional", after)
        self.assertEqual(after.count("{% block description %}"), 1)

    def test_contact_adds_safe_meta_when_missing(self):
        before = (
            '{% extends "personal_site/base.html" %}'
            '{% block content %}<p>LOCATION</p><strong>Vancouver, British Columbia, Canada</strong>'
            '<form method="post"><input name="csrfmiddlewaretoken"></form>{% endblock %}'
        )
        after = mod.revise_contact(before)
        self.assertNotIn("Vancouver", after)
        self.assertIn("International &amp; remote collaboration", after)
        self.assertIn("name=\"csrfmiddlewaretoken\"", after)
        self.assertEqual(after.count("{% block description %}"), 1)

    def test_nonstandard_location_requires_manual_review(self):
        with self.assertRaises(ValueError):
            mod.revise_contact('{% extends "x" %}LOCATION Berlin, Germany')
        with self.assertRaises(ValueError):
            mod.revise_about('{% extends "x" %}Vancouver')

    def test_no_mass_directory_scope(self):
        self.assertEqual(len(mod.RELATIVES), 2)
        self.assertEqual(
            mod.RELATIVES,
            (
                "templates/personal_site/core/about.html",
                "templates/personal_site/core/contact.html",
            ),
        )
        self.assertNotIn("public_html", str(mod.APP))

    def test_separate_metadata_source_replacement(self):
        original = 'meta_description = "Professional collaboration in Vancouver or remotely."'
        updated = mod.strict_replace(original, mod.SEO_OLD, mod.SEO_NEW, "Contact SEO")
        self.assertNotIn("Vancouver", updated)
        self.assertIn("international and remote teams", updated)
        with self.assertRaises(ValueError):
            mod.strict_replace(updated, mod.SEO_OLD, mod.SEO_NEW, "Contact SEO")

    def test_duplicate_meta_block_rejected(self):
        with self.assertRaises(ValueError):
            mod.description(
                "{% block description %}one{% endblock %}{% block description %}two{% endblock %}",
                "new",
            )


if __name__ == "__main__":
    unittest.main()
