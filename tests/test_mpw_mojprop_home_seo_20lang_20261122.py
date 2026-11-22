"""Offline regression tests for the live MOJ PROP homepage SEO release."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mpw_home_seo_20lang",
    ROOT / "scripts" / "mpw_mojprop_home_seo_20lang_20261122.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MojPropHomeSEO20LangTests(TestCase):
    def test_release_pins_the_verified_live_before_and_after(self):
        self.assertEqual(
            MODULE.BASE_SHA256,
            "b76f16876d093900f6f855c5771f6ff3ebe374450a0c373dcb57f47635e0bc07",
        )
        self.assertEqual(
            MODULE.CANDIDATE_SHA256,
            "3b2b8dd9271ba059cf5df1dff6c09533100cceb1730ae5f30993a443e0be87f5",
        )
        self.assertEqual(MODULE.BASE_BYTES, 266520)
        self.assertEqual(MODULE.CANDIDATE_BYTES, 267908)

    def test_synthetic_patch_changes_only_the_four_expected_anchors(self):
        before = (
            '<section id="mpw-mojprop-spotlight-20261121">'
            + MODULE.OLD_H1
            + MODULE.OLD_SUBTITLE
            + MODULE.OLD_LEAD
            + MODULE.OLD_LANGUAGE_LINK
            + "</section>"
        ).encode("utf-8")
        after = (
            before.decode("utf-8")
            .replace(MODULE.OLD_H1, MODULE.NEW_H1, 1)
            .replace(MODULE.OLD_SUBTITLE, MODULE.NEW_SUBTITLE, 1)
            .replace(MODULE.OLD_LEAD, MODULE.NEW_LEAD, 1)
            .replace(MODULE.OLD_LANGUAGE_LINK, MODULE.NEW_LANGUAGE_LINK, 1)
            .encode("utf-8")
        )
        with (
            patch.object(MODULE, "BASE_SHA256", MODULE.digest(before)),
            patch.object(MODULE, "BASE_BYTES", len(before)),
            patch.object(MODULE, "CANDIDATE_SHA256", MODULE.digest(after)),
            patch.object(MODULE, "CANDIDATE_BYTES", len(after)),
        ):
            candidate = MODULE.derive(before)
        self.assertEqual(candidate, after)
        self.assertIn("MOJ <em>PROP</em>", candidate.decode("utf-8"))
        self.assertEqual(candidate.decode("utf-8").count("href=\"/moj-prop/languages/"), 19)
        self.assertIn('href="/moj-prop/" lang="en">English</a>', candidate.decode("utf-8"))

    def test_wrong_source_is_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "LIVE_SOURCE_SHA_MISMATCH"):
            MODULE.derive(b"unreviewed live homepage")


if __name__ == "__main__":
    import unittest

    unittest.main()
