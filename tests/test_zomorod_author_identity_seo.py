"""Regression checks for the public Persian author profile.

These validate source markup only. A separate live check must confirm that the
server actually serves this file instead of redirecting to the English page.
"""

import json
from html.parser import HTMLParser
from pathlib import Path
import unittest
from scripts.zomorod_author_profile_route_release_20261023 import (
    REDIRECT, PERSIAN_URL, OLD_IMPORT, NEW_IMPORT, OLD_ROUTE, NEW_ROUTE,
    OLD_SITEMAP_ITEM, NEW_SITEMAP_ITEM, SEO_VIEW_MARKER,
    with_django_author_route, with_django_author_view_and_sitemap,
    with_persian_sitemap_entry, without_exact_redirect,
    verified_author_redirect_state,
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
            {org["url"] for org in person["worksFor"]},
            {"https://zomorodmelal.ir/", "https://mojplaywin.com/"},
        )
        self.assertEqual(person["homeLocation"]["name"], "Vancouver, British Columbia, Canada")
        self.assertIn("مدیرعامل مج‌پلی‌وین", " ".join(person["jobTitle"]))
        self.assertIn("ونکوور", self.source)
        self.assertIn("پژوهش و تحقیقات علمی", self.source)
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

    def test_idempotent_live_author_redirect_state_is_scoped(self):
        self.assertEqual(verified_author_redirect_state(REDIRECT + b"\n"), b"")
        clean = b'PassengerAppRoot "/home/zomorod2/Saeit"\n'
        self.assertEqual(verified_author_redirect_state(clean), clean)
        with self.assertRaises(ValueError):
            verified_author_redirect_state(b"Redirect 301 /authors/mojtaba-rozegar /unexpected\n")

    def test_only_one_canonical_persian_url_is_added_to_sitemap(self):
        original = (
            b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b'<url><loc>https://zomorodmelal.ir/</loc></url></urlset>'
        )
        updated = with_persian_sitemap_entry(original)
        self.assertEqual(updated.count(PERSIAN_URL.encode()), 1)
        self.assertIn(b"https://zomorodmelal.ir/", updated)
        self.assertEqual(with_persian_sitemap_entry(updated), updated)
        with self.assertRaises(ValueError):
            with_persian_sitemap_entry(b"<html/>")

    def test_django_route_and_dynamic_sitemap_fix_match_repo_source(self):
        root = PROFILE.parents[3]
        urls = (root / "config/urls.py").read_text(encoding="utf-8")
        seo = (root / "core/seo_views.py").read_text(encoding="utf-8")
        self.assertIn(NEW_IMPORT, urls)
        self.assertIn(NEW_ROUTE, urls)
        self.assertNotIn(OLD_ROUTE, urls)
        self.assertIn(NEW_SITEMAP_ITEM, seo)
        self.assertIn(SEO_VIEW_MARKER, seo)
        self.assertIn('content_type="text/html; charset=utf-8"', seo)
        old_urls = urls.replace(NEW_IMPORT, OLD_IMPORT).replace(NEW_ROUTE, OLD_ROUTE)
        self.assertEqual(with_django_author_route(old_urls.encode()).decode(), urls)
        old_seo = (
            'urls = [' + OLD_SITEMAP_ITEM + ']\n'
        ).replace(']]', ']')  # small, syntactically valid standalone source
        updated = with_django_author_view_and_sitemap(old_seo.encode()).decode()
        self.assertIn(NEW_SITEMAP_ITEM, updated)
        self.assertIn(SEO_VIEW_MARKER, updated)


if __name__ == "__main__":
    unittest.main()
