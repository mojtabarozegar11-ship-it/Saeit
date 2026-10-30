import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mpw_gsc_meta_tag_20261030 as m


class GoogleOwnershipTagTests(unittest.TestCase):
    def setUp(self):
        self.original = (
            b'<!doctype html><html lang="en"><head>\n'
            + m.TITLE
            + b'\n<meta name="description" content="Keep it."></head>'
            + b'<body><h1>Keep the real homepage</h1></body></html>'
        )

    def test_exact_insertion_only_in_head(self):
        updated = m.patch(self.original)
        self.assertEqual(updated.count(m.META), 1)
        self.assertEqual(updated.replace(b"\n  " + m.META, b""), self.original)
        self.assertLess(updated.index(m.META), updated.index(b"</head>"))
        self.assertLess(updated.index(m.META), updated.index(b"<body"))

    def test_idempotent(self):
        once = m.patch(self.original)
        self.assertEqual(m.patch(once), once)

    def test_preserve_legacy_and_child_links(self):
        source = self.original.replace(b"Keep the real homepage", b"/store/ /saman/ /mojtaba.roozegar/")
        changed = m.patch(source)
        for url in (b"/store/", b"/saman/", b"/mojtaba.roozegar/"):
            self.assertIn(url, changed)
        self.assertEqual(changed.replace(b"\n  " + m.META, b""), source)

    def test_refuse_unknown_home(self):
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            m.patch(self.original.replace(m.TITLE, b"<title>Other site</title>"))

    def test_refuse_foreign_google_owner(self):
        with self.assertRaisesRegex(ValueError, "Foreign"):
            m.patch(self.original.replace(b"</head>", b'<meta name="google-site-verification" content="other"></head>'))

    def test_refuse_duplicate_head(self):
        with self.assertRaisesRegex(ValueError, "head"):
            m.patch(self.original.replace(b"</head>", b"</head><head></head>"))


if __name__ == "__main__":
    unittest.main()
