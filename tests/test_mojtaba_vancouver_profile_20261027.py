"""Owner-confirmed Vancouver, complete training and role, scoped deploy guards."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mojtaba_vancouver", ROOT / "scripts/mojtaba_vancouver_profile_20261027.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def about_source():
    return """
{% extends "personal_site/base.html" %}
{% block description %}Mojtaba Roozegar is an entrepreneur.{% endblock %}
{% block content %}
<h1>About Me.</h1>
<p>I am Mojtaba Roozegar, an entrepreneur and researcher from Iran, with an interest in research and professional collaboration across borders.</p>
<p>I currently serve as CEO of Zomorod Melal Agro-Industry Company, managing agricultural and scientific projects, and professional work in jewelry, gold coins, carpet trading, hospitality, research, writing and website development.</p>
<div class="mpw-fact"><dt>Field</dt><dd>Production Economics and Farm Management</dd></div>
<p>Universiti Putra Malaysia (UPM) awarded a PhD in Agricultural Economics.</p>
{% endblock %}
"""


class VancouverBiographyTests(unittest.TestCase):
    def test_restores_current_residence_and_roles(self):
        after = mod.revise_about(about_source())
        self.assertIn("living in Vancouver, British Columbia, Canada", after)
        self.assertIn("<dt>Current residence</dt>", after)
        self.assertIn("Zomorod Melal Agro-Industry Company", after)
        self.assertIn("MojPlayWin", after)
        self.assertIn("gemstones", after)
        self.assertIn("professional education", after)
        self.assertIn("PhD in Agricultural Economics", after)
        self.assertEqual(after.count("{% block description %}"), 1)
        with self.assertRaises(ValueError):
            mod.revise_about(after)

    def test_contact_preserves_csrf_and_collaboration(self):
        before = ('{% extends "personal_site/base.html" %}'
                  '{% block content %}<p>International &amp; remote collaboration</p>'
                  '<form method="post">{% csrf_token %}</form>{% endblock %}')
        after = mod.revise_contact(before)
        self.assertIn("Vancouver, British Columbia, Canada", after)
        self.assertIn("International &amp; remote collaboration", after)
        self.assertIn("{% csrf_token %}", after)
        with self.assertRaises(ValueError):
            mod.revise_contact(after)

    def test_requires_existing_verified_source_content(self):
        with self.assertRaises(ValueError):
            mod.revise_about('{% extends "personal_site/base.html" %}random')
        with self.assertRaises(ValueError):
            mod.revise_contact('{% extends "personal_site/base.html" %}<p>Toronto</p>')

    def test_metadata_deduplicates_existing_copy(self):
        before = ('<meta name="description" content="collaboration across international and remote teams">\n'
                  '<meta property="og:description" content="collaboration across international and remote teams">')
        after = mod.revise_shared_meta(before)
        self.assertEqual(after.count("Vancouver, British Columbia, Canada"), 2)
        self.assertEqual(after.count(mod.SEO_OLD), 0)
        with self.assertRaises(ValueError):
            mod.revise_shared_meta('one across international and remote teams')

    def test_scope_is_personal_app_only(self):
        self.assertEqual(mod.RELATIVES, (
            "templates/personal_site/core/about.html",
            "templates/personal_site/core/contact.html",
        ))
        self.assertNotIn("public_html", str(mod.APP))
        self.assertIn("/mojtaba_personal/", str(mod.APP))
        self.assertIn("/.backups/mojtaba-residence-profession", str(mod.BACKUP_ROOT))


if __name__ == "__main__":
    unittest.main()
