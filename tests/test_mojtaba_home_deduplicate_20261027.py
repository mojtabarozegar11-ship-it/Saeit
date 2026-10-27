"""Regression and safety tests for the independent Mojtaba home consolidation."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mojtaba_home_deduplicate",
    ROOT / "scripts/mojtaba_home_deduplicate_20261027.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture():
    parts = [
        '{% extends "personal_site/base.html" %}',
        "{% block content %}",
        '<section id="mpw-primary-personal-profile-20261016">',
        '<figure><img src="/assets/personal_site/official_profile_20261016/portrait.2935ce8cb70d.webp" alt="Mojtaba Roozegar"></figure>',
        "<p>PROFESSIONAL PROFILE</p>",
        "<p>Research and professional collaboration.</p>",
        '<a href="/mojtaba.roozegar/contact/">Discuss a professional collaboration</a>',
        "</section>",
        '<section class="hero"><div class="hero-layout">',
        '<h1 id="hero-title">Mojtaba Roozegar</h1>',
        '<div class="hero-visual"><img src="/uploads/profile/mojtaba-roozegar.jpg" alt="Mojtaba"></div>',
        "</div></section>",
        '<section id="mpw-social-central-hub-20261026"><h2>Official connections</h2></section>',
        '<nav class="mpw-complete-toc" id="mpw-complete-standard-20261019-toc">Navigate</nav>',
        '<section id="owner-original-gallery-20261015"><h2>Original gallery</h2></section>',
    ]
    for num, ident in enumerate(mod.DUPLICATE_IDS):
        parts.append('<section id="' + ident + '"><h2>Journal section ' + str(num) + '</h2>')
        parts.append("<section><p>" + str(num) * 8000 + "</p></section>")
        parts.append("</section>")
    parts.append("<p>End of original personal home. Contact and legal pages remain unchanged.</p>")
    parts.append("{% endblock %}")
    return "\n".join(parts)


def journal_fixture():
    home = fixture()
    return "\n".join(mod.section_text(home, item) for item in mod.DUPLICATE_IDS)


class HomeDeduplicationTests(unittest.TestCase):
    def test_exact_public_section_copy_check(self):
        mod.assert_duplicate_equivalence(fixture(), journal_fixture())

    def test_fails_on_changed_journal_material(self):
        changed = journal_fixture().replace("Journal section 0", "Journal section different")
        with self.assertRaisesRegex(ValueError, "Journal differs"):
            mod.assert_duplicate_equivalence(fixture(), changed)

    def test_remove_ten_sections_preserves_all_original_routes_and_unique_content(self):
        old = fixture()
        new, count = mod.remove_duplicate_sections(old)
        self.assertGreaterEqual(count, 75000)
        for ident in mod.DUPLICATE_IDS:
            self.assertNotIn(ident, new)
        for ident in mod.PRESERVE_IDS:
            self.assertIn('id="' + ident + '"', new)
        self.assertIn("End of original personal home", new)
        self.assertEqual(old.count("{%"), new.count("{%"))

    def test_complete_single_intro_and_ten_section_cleanup(self):
        old = fixture()
        result, removed = mod.plan(old)
        self.assertGreater(removed, 75000)
        self.assertIn('id="mpw-two-profile-portraits-20261020"', result)
        self.assertEqual(result.count('id="hero-title"'), 1)
        self.assertNotIn("PROFESSIONAL PROFILE", result)
        self.assertEqual(result.count("<img"), 2)
        self.assertIn("mpw-social-central-hub-20261026", result)
        self.assertIn("owner-original-gallery-20261015", result)
        for ident in mod.DUPLICATE_IDS:
            self.assertNotIn(ident, result)

    def test_partial_or_missing_section_fails_closed(self):
        src = fixture().replace(
            'id="mpw-journal-longform-index-20261016"',
            'id="changed-section"',
        )
        with self.assertRaises(ValueError):
            mod.remove_duplicate_sections(src)

    def test_nested_duplicate_overlap_refused(self):
        src = fixture()
        first = mod.DUPLICATE_IDS[0]
        second = mod.DUPLICATE_IDS[1]
        nested = (
            '<section id="' + first + '">'
            '<section id="' + second + '">nested</section></section>'
        )
        src = src.replace(mod.section_text(src, first), nested)
        with self.assertRaises(ValueError):
            mod.remove_duplicate_sections(src)

    def test_duplicate_with_complete_django_tags_can_be_removed(self):
        original = fixture()
        ident = mod.DUPLICATE_IDS[0]
        fragment = mod.section_text(original, ident)
        tagged = fragment.replace("<h2>", "{% if show %}<h2>", 1).replace(
            "</h2>", "</h2>{% endif %}", 1,
        )
        source = original.replace(fragment, tagged, 1)
        updated, removed = mod.remove_duplicate_sections(source)
        self.assertGreater(removed, 75000)
        self.assertIn("{% extends", updated)
        self.assertNotIn("{% if show %}", updated)
        self.assertNotIn(ident, updated)

    def test_release_checks_element_not_shared_css_selector(self):
        workflow = (ROOT / ".github/workflows/mojtaba-home-deduplicate-20261027.yml").read_text(encoding="utf-8")
        self.assertIn("'id=\"mpw-journal-longform-index-20261016\"' in doc", workflow)
        self.assertIn("HOME_HTML_STILL_TOO_LARGE", workflow)
        self.assertIn("PUBLIC_HOME_HTML_STILL_TOO_LARGE", workflow)
        self.assertNotIn("if 'mpw-journal-longform-index-20261016' in doc:", workflow)

    def test_boundary_is_one_independent_template(self):
        self.assertEqual(mod.REL, "templates/personal_site/core/home.html")
        self.assertIn("/mojtaba_personal/mojtaba_roozegar_personal_v17", str(mod.APP))
        self.assertNotIn("public_html", str(mod.APP / mod.REL))
        self.assertEqual(len(mod.DUPLICATE_IDS), 10)
        self.assertEqual(len(set(mod.DUPLICATE_IDS)), 10)


if __name__ == "__main__":
    unittest.main()
