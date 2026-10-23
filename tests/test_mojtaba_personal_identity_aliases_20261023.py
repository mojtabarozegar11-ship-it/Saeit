"""Pure source checks for the personal-site identity JSON-LD upgrader."""

import json
import re
import unittest

from scripts.mojtaba_personal_identity_aliases_20261023 import (
    IDENTIFIER, NAMES, PHOTO, upgrade,
)


PERSON = {
    "@type": "ProfilePage",
    "mainEntity": {
        "@type": "Person", "@id": IDENTIFIER,
        "name": "Mojtaba Roozegar", "alternateName": "مجتبی روزگار",
        "url": "https://mojplaywin.com/mojtaba.roozegar/",
        "sameAs": ["https://zomorodmelal.ir/authors/mojtaba-rozegar/"],
    },
}


def fixture(person=PERSON):
    return (
        '{% block title %}Existing title{% endblock %}'
        '<link rel="canonical" href="https://mojplaywin.com/mojtaba.roozegar/">'
        '<script type="application/ld+json">'
        + json.dumps(person, ensure_ascii=False)
        + '</script><p>Unmodified professional profile</p>'
    )


class PersonalIdentityAliasesTests(unittest.TestCase):
    def test_requested_spellings_and_real_photo_in_existing_person_schema(self):
        old = fixture()
        new = upgrade(old)
        obj = json.loads(
            re.search(r'<script type="application/ld\+json">(.*?)</script>', new)
            .group(1)
        )
        self.assertEqual(obj["@type"], "ProfilePage")
        self.assertEqual(obj["mainEntity"]["name"], "Mojtaba Roozegar")
        self.assertTrue(set(NAMES).issubset(set(obj["mainEntity"]["alternateName"])))
        self.assertEqual(obj["mainEntity"]["image"], PHOTO)
        self.assertEqual(obj["mainEntity"]["honorificPrefix"], "Dr.")
        self.assertIn("<p>Unmodified professional profile</p>", new)
        self.assertIn("{% block title %}Existing title{% endblock %}", new)
        self.assertEqual(new, upgrade(new))

    def test_no_duplicate_or_wrong_person_is_mutated(self):
        with self.assertRaises(ValueError):
            upgrade(fixture() + fixture())
        wrong = json.loads(json.dumps(PERSON))
        wrong["mainEntity"]["name"] = "Someone Else"
        with self.assertRaises(ValueError):
            upgrade(fixture(wrong))


if __name__ == "__main__":
    unittest.main()
