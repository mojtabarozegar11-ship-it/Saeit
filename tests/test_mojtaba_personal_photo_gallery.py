"""Non-destructive offline tests for personal gallery content generation."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "mojtaba_personal_photo_gallery.py"
SPEC = importlib.util.spec_from_file_location("mojtaba_personal_photo_gallery", MODULE)
GALLERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GALLERY)

class PersonalPhotoGalleryTests(unittest.TestCase):
    def setUp(self):
        self.home = "{% extends 'personal_site/base.html' %}{% load static %}\n{% block content %}\n<h1>Mojtaba Roozegar</h1>\n{% endblock %}\n"

    def test_additive_only(self):
        changed = GALLERY.prepare_home(self.home)
        self.assertIn("<h1>Mojtaba Roozegar</h1>", changed)
        self.assertTrue(changed.startswith("{% extends"))
        self.assertEqual(changed.count(GALLERY.MARKER), 1)
        self.assertEqual(changed.count('class="og-card"'), 10)
        self.assertEqual(changed.count("{% block content %}"), 1)
        self.assertEqual(changed.count("{% endblock %}"), 1)

    def test_all_photos_referenced_once(self):
        changed = GALLERY.prepare_home(self.home)
        for i in range(1, 11):
            self.assertEqual(changed.count("photo-%02d.jpg" % i), 2)
        self.assertNotIn("noindex", changed.lower())

    def test_duplicate_and_mismatched_template_refused(self):
        changed = GALLERY.prepare_home(self.home)
        with self.assertRaises(ValueError):
            GALLERY.prepare_home(changed)
        with self.assertRaises(ValueError):
            GALLERY.prepare_home("<h1>Mojtaba</h1>")

    def test_expected_images_unique(self):
        self.assertEqual(len(GALLERY.PHOTOS), 10)
        self.assertEqual(len({item[1] for item in GALLERY.PHOTOS}), 10)
        self.assertTrue(all(len(item[1]) == 64 for item in GALLERY.PHOTOS))

if __name__ == "__main__":
    unittest.main()
