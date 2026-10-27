"""Safety regressions for Mojtaba's image-gallery homepage consolidation."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mojtaba_gallery_consolidate",
    ROOT / "scripts/mojtaba_gallery_consolidate_20261027.py",
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def image(i):
    return "/mojtaba.roozegar/assets/personal_site/owner_gallery_20261015/photo-%02d.jpg" % i


REPEATED = "/mojtaba.roozegar/assets/personal_site/owner_gallery_20261015_b/photo-09.png"


def sample_home():
    parts = ['{% extends "personal_site/base.html" %}', "{% block content %}"]
    for ident in mod.PRESERVE_IDS:
        parts.append('<div id="' + ident + '">Protected text and brand content</div>')
    parts.append('<section id="' + mod.GALLERY_ID + '"><h2>Original Gallery</h2>')
    parts.extend('<figure><a href="' + image(i) + '"><img src="' + image(i) + '" alt="Photo"></a></figure>' for i in range(1, 11))
    parts.append("</section>")
    parts.append('<section id="' + mod.PORTRAITS_ID + '">')
    parts.extend('<img src="' + REPEATED + '" alt="Portrait">' for _ in range(3))
    parts.append("</section>")
    parts.extend(["<section><p>Keep this unique personal note</p></section>", "{% endblock %}"])
    return "\n".join(parts)


def sample_gallery():
    return "<main>" + "".join(
        '<img src="' + image(i) + '" alt="Original">' for i in range(1, 11)
    ) + '<img src="' + REPEATED + '" alt="Second album"></main>'


class GalleryConsolidationTests(unittest.TestCase):
    def test_gallery_contains_all_thirteen_homepage_images(self):
        mod.assert_gallery_retains_images(sample_home(), sample_gallery())

    def test_missing_gallery_asset_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing an image"):
            mod.assert_gallery_retains_images(
                sample_home(), sample_gallery().replace(image(8), "/missing.jpg")
            )

    def test_changed_repeated_portrait_fails_closed(self):
        altered = sample_home().replace(REPEATED, "/changed.jpg", 1)
        with self.assertRaisesRegex(ValueError, "Three-copy"):
            mod.assert_gallery_retains_images(altered, sample_gallery())

    def test_two_gallery_sections_removed_but_other_material_preserved(self):
        source = sample_home()
        result, removed = mod.plan(source)
        self.assertGreater(removed, 5000)
        self.assertLess(len(result), len(source))
        self.assertEqual(result.count('id="' + mod.NEW_ID + '"'), 1)
        self.assertIn('/mojtaba.roozegar/gallery/', result)
        self.assertIn("Keep this unique personal note", result)
        for ident in mod.PRESERVE_IDS:
            self.assertEqual(result.count('id="' + ident + '"'), 1)
        for ident in (mod.GALLERY_ID, mod.PORTRAITS_ID):
            self.assertNotIn('id="' + ident + '"', result)
        self.assertNotIn("<img", result)

    def test_rerun_refuses_double_mutation(self):
        result, _ = mod.plan(sample_home())
        with self.assertRaises(ValueError):
            mod.plan(result)

    def test_missing_or_nested_original_section_fails(self):
        source = sample_home().replace(
            'id="' + mod.GALLERY_ID + '"', 'id="changed-gallery"'
        )
        with self.assertRaises(ValueError):
            mod.plan(source)

    def test_target_is_independent_personal_home_only(self):
        self.assertEqual(mod.REL, "templates/personal_site/core/home.html")
        self.assertIn("/mojtaba_personal/", str(mod.APP))
        self.assertNotIn("public_html", str(mod.APP / mod.REL))
        self.assertEqual(len(mod.PRESERVE_IDS), 7)


if __name__ == "__main__":
    unittest.main()
