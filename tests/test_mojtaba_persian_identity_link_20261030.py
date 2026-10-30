"""Offline checks for the scoped, visible Persian author-profile link."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mojtaba_persian_identity_link_20261030.py"
spec = importlib.util.spec_from_file_location("fa_identity", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

BASE = (
    '{% extends "personal_site/base.html" %}\n'
    '<h1 id="hero-title">Mojtaba Roozegar</h1>\n'
    '<p class="hero-intro">Mojtaba Roozegar (مجتبی روزگار) '
    'is based in Vancouver, Canada.</p>\n'
    '<section id="other">Preserve existing sections unchanged.</section>'
)


class PersianProfileLinkTests(unittest.TestCase):
    def test_exact_bilingual_link_and_unchanged_sections(self):
        result = mod.transform(BASE)
        self.assertEqual(result.count(mod.MARKER), 1)
        self.assertEqual(result.count(mod.PERSIAN_URL), 1)
        self.assertIn('lang="fa" dir="rtl"', result)
        self.assertIn('زندگی‌نامه رسمی مجتبی روزگار', result)
        self.assertIn('<section id="other">Preserve existing sections unchanged.</section>', result)
        self.assertEqual(result.count('id="hero-title"'), 1)

    def test_not_idempotent_duplicate_protection(self):
        with self.assertRaises(ValueError):
            mod.transform(mod.transform(BASE))

    def test_reject_changed_identity_or_residence_or_layout(self):
        for altered in (
            BASE.replace("Vancouver, Canada", "somewhere"),
            BASE.replace("مجتبی روزگار", "another person"),
            BASE.replace('id="hero-title"', 'id="hero"'),
            BASE + '<p class="hero-intro">another hero</p>',
        ):
            with self.subTest(altered=altered[-80:]):
                with self.assertRaises(ValueError):
                    mod.transform(altered)

    def test_strict_file_scope(self):
        self.assertEqual(mod.REL, "templates/personal_site/core/home.html")
        self.assertNotIn("public_html", str(mod.APP))
        self.assertTrue(str(mod.PERSIAN_URL).startswith("https://"))


if __name__ == "__main__":
    unittest.main()
