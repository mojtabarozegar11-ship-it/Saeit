"""Regression checks for the public Persian author profile.

These validate source markup only. A separate live check must confirm that the
server actually serves this file instead of redirecting to the English page.
"""

import json
from html.parser import HTMLParser
from pathlib import Path
import unittest
from scripts.zomorod_author_profile_route_release_20261023 import (
    REDIRECT, without_exact_redirect,
)


PROFILE = (
    Path(__file__).resolve().parents[1]
    / "public/authors/mojtaba-rozegar/index.html"
)
PORTRAIT = (
    "https://zomorodmelal.ir/static/site/"
    "zomorod-about/ceo-mojtaba-rozegar.webp"
)


class ProfileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.meta = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "meta":
            self.meta.append(attrs)
        if tag == "link":
            self.links.append(attrs)


class PersianAuthorSeoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PROFILE.read_text(encoding="utf-8")
        cls.parser = ProfileParser()
        cls.parser.feed(cls.source)
        cls.data = json.loads(
            cls.source.split('<script type="application/ld+json">', 1)[1]
            .split("</script>", 1)[0]
        )

    def test_authentic_portrait_is_before_biography_and_visible_on_all_sizes(self):
        source = self.source
        self.assertLess(source.index("<figure>"), source.index('id="profile-name"'))
        self.assertIn('src="' + PORTRAIT + '"', source)
        self.assertIn("flex-direction:column", source)
        self.assertNotIn("display:none", source)
        images = [a for tag, a in self.parser.tags if tag == "img"]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["src"], PORTRAIT)
        self.assertIn("مجتبی روزگار", images[0]["alt"])

    def test_canonical_and_reciprocal_language_targets(self):
        canonical = [
            a["href"] for a in self.parser.links if a.get("rel") == "canonical"
        ]
        self.assertEqual(canonical, [
            "https://zomorodmelal.ir/authors/mojtaba-rozegar/"
        ])
        alternate = {
            a["hreflang"]: a["href"]
            for a in self.parser.links if a.get("rel") == "alternate"
        }
        self.assertEqual(alternate["fa-IR"], canonical[0])
        self.assertEqual(
            alternate["en"],
            "https://zomorodmelal.ir/en/authors/mojtaba-rozegar/",
        )
        self.assertNotIn("noindex", self.source)

    def test_one_person_identity_with_requested_spellings(self):
        self.assertEqual(self.data["@type"], "ProfilePage")
        person = self.data["mainEntity"]
        self.assertEqual(person["name"], "مجتبی روزگار")
        self.assertEqual(person["image"], PORTRAIT)
        self.assertTrue({
            "روزگار", "Roozegar", "مجتبی روزگار", "Mojtaba Roozegar",
            "دکتر مجتبی روزگار", "Dr.mojtaba.rozegar",
        }.issubset(set(person["alternateName"])))
        self.assertEqual(
            person["worksFor"]["url"], "https://zomorodmelal.ir/"
        )
        self.assertIn(
            "https://mojplaywin.com/mojtaba.roozegar/",
            person["sameAs"],
        )

    def test_one_exact_redirect_removed_without_other_apache_changes(self):
        other = (
            b'PassengerAppRoot "/home/zomorod2/Saeit"\n'
            b"Redirect 301 /legacy /new\n"
        )
        self.assertEqual(
            without_exact_redirect(REDIRECT + b"\n" + other), other
        )
        with self.assertRaises(ValueError):
            without_exact_redirect(other)
        with self.assertRaises(ValueError):
            without_exact_redirect(REDIRECT + b"\n" + REDIRECT + b"\n" + other)
        with self.assertRaises(ValueError):
            without_exact_redirect(other + REDIRECT + b"\n")


if __name__ == "__main__":
    unittest.main()
