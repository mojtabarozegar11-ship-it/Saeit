from pathlib import Path
import importlib.util
import unittest

spec = importlib.util.spec_from_file_location(
    "photos", Path(__file__).resolve().parents[1] / "scripts/mojtaba_fill_last_three_images.py"
)
photos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(photos)

class FounderPhotoPagesTests(unittest.TestCase):
    def template(self):
        return """{% extends 'personal_site/base.html' %}{% load static %}
{% block content %}
<div class="mpw-inner" id="mpw-inner-content-20261015">
<style>original styles</style>
<h2>The heading</h2>
<p class="mpw-intro">Original introduction remains unchanged.</p>
<div class="mpw-journey"><p>Original content must not change.</p></div>
</div>{% endblock %}
"""
    def test_all_three_are_additive(self):
        for page in photos.PAGES:
            with self.subTest(page=page):
                original = self.template()
                result = photos.patch(page, original)
                self.assertIn("Original introduction remains unchanged.", result)
                self.assertIn("Original content must not change.", result)
                self.assertEqual(result.count(photos.MARKER), 1)
                self.assertEqual(result.count('<figure>'), len(photos.PAGES[page]))
                self.assertEqual(result.count('{% block content %}'), 1)
                self.assertEqual(result.count('{% endblock %}'), 1)
                with self.assertRaises(ValueError):
                    photos.patch(page, result)
    def test_photo_refs_are_original_only(self):
        for page, images in photos.PAGES.items():
            changed = photos.patch(page, self.template())
            for i,title,caption in images:
                self.assertGreaterEqual(i, 1)
                self.assertLessEqual(i, 10)
                self.assertEqual(changed.count(f"photo-{i:02d}.jpg"), 2)
                self.assertIn(title,changed)
                self.assertIn("editorial",caption.lower())
            self.assertNotIn("images.unsplash.com",changed)
            self.assertNotIn("imagegen",changed.lower())
    def test_existing_real_site_template_marker_required(self):
        with self.assertRaises(ValueError):
            photos.patch("resume", "{% load static %}<p class=\"mpw-intro\">Hello</p>")
        with self.assertRaises(ValueError):
            photos.patch("about", self.template())
        with self.assertRaises(ValueError):
            photos.patch("resume", self.template().replace("{% load static %}",""))
    def test_no_duplicated_photos_per_page(self):
        for page,photoset in photos.PAGES.items():
            self.assertEqual(len({p[0] for p in photoset}), len(photoset))

if __name__=="__main__":
    unittest.main()
