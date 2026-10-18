import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from mojtaba_second_10_owner_photos import addition as original_addition
from mojtaba_personal_home_sport_white_only_20261018 import patch, PHOTO_TAG, NEW_MARKER, SOURCE_CAPTIONS

class PersonalHomeSportsPortraitTests(unittest.TestCase):
    def setUp(self):
        self.original = (
            '{% extends "personal_site/base.html" %}\n'
            '{% load static %}\n'
            '{% block content %}\n'
            '<h1>Mojtaba Roozegar</h1>\n'
            '<div id="research-articles">Prior articles stay visible.</div>\n'
            + original_addition("home") + "\n"
            '<div id="contact">Contact information remains unchanged.</div>\n'
            '{% endblock %}'
        )

    def test_exact_original_screenshot_cards(self):
        self.assertIn("Personal executive portrait", self.original)
        self.assertIn("Executive close-up portrait", self.original)
        self.assertIn("Four professional portrait views", self.original)

    def test_replaces_only_three_unwanted_home_cards(self):
        new = patch(self.original)
        self.assertIn(NEW_MARKER, new)
        self.assertEqual(new.count('class="mpw-portrait-card'), 3)
        self.assertEqual(new.count(PHOTO_TAG), 3)
        for label in SOURCE_CAPTIONS:
            self.assertNotIn(label, new)
        self.assertIn("Casual sport portrait", new)
        self.assertIn("Outdoor sport-jacket portrait", new)
        self.assertIn("White-shirt portrait", new)
        self.assertIn('style="--sport-photo-x:0%"', new)
        self.assertIn('style="--sport-photo-x:-75%"', new)
        self.assertIn('style="--sport-photo-x:-50%"', new)
        for part in (
            '<h1>Mojtaba Roozegar</h1>',
            '<div id="research-articles">Prior articles stay visible.</div>',
            '<div id="contact">Contact information remains unchanged.</div>',
        ):
            self.assertIn(part,new)
        self.assertEqual(new.count("{% block content %}"),1)
        self.assertEqual(new.count("{% endblock %}"),1)

    def test_fail_closed_if_already_changed(self):
        new=patch(self.original)
        with self.assertRaises(RuntimeError):
            patch(new)

    def test_fail_closed_if_a_source_card_absent(self):
        with self.assertRaises(RuntimeError):
            patch(self.original.replace("Executive close-up portrait","changed",1))

    def test_all_other_site_routes_are_absent(self):
        new=patch(self.original)
        self.assertNotIn("Passenger",new)
        self.assertNotIn("/store/",new)
        self.assertNotIn("mojtaba_personal/mojtaba_roozegar_personal_v17/templates/personal_site/core/about.html",new)

if __name__=="__main__":
    unittest.main()
