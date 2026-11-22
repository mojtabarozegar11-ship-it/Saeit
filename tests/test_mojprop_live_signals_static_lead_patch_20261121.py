"""No-network regression for exact live signals static CTA candidate."""
import hashlib
import unittest
from unittest.mock import patch

from scripts import mojprop_live_signals_static_lead_patch_20261121 as m


class LiveSignalsStaticCTAPatchTests(unittest.TestCase):
    ORIGINAL = (
        b'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        b'<title>Signals</title></head><body>'
        b'<nav><a href="/moj-prop/#request">Start a request</a></nav>'
        b'<main><h1>Market research</h1><p>Educational; no subscription.</p>'
        b'</main><script defer src="/mpw-measure/tracker.js"></script></body></html>'
    )

    def candidate(self, source):
        expected = source.replace(m.ORIGINAL, m.REPLACEMENT, 1)
        with patch.object(m, "SOURCE_SHA256", hashlib.sha256(source).hexdigest()), \
             patch.object(m, "CANDIDATE_SHA256", hashlib.sha256(expected).hexdigest()):
            return m.generate_candidate(source)

    def test_only_approved_nav_anchor_changes(self):
        changed = self.candidate(self.ORIGINAL)
        self.assertEqual(changed.replace(m.REPLACEMENT, m.ORIGINAL, 1), self.ORIGINAL)
        self.assertEqual(changed.count(b"service=signals"), 1)
        self.assertIn(b"Request a free written signal proposal", changed)
        self.assertEqual(changed.count(b"utm_source=moj_prop"), 1)
        self.assertEqual(changed.count(b"utm_medium=onsite"), 1)
        self.assertIn(b"utm_campaign=signals_education_lead_20261121", changed)
        self.assertIn(b"utm_content=signal_nav", changed)
        self.assertIn(b'<script defer src="/mpw-measure/tracker.js"></script>', changed)
        self.assertNotIn(b'/mojprop-starter30-checkout/', changed)

    def test_drift_is_refused(self):
        with self.assertRaisesRegex(ValueError, "source SHA256 drift"):
            m.generate_candidate(self.ORIGINAL)
        with self.assertRaisesRegex(ValueError, "candidate drift"):
            with patch.object(m, "SOURCE_SHA256", hashlib.sha256(self.ORIGINAL).hexdigest()):
                m.generate_candidate(self.ORIGINAL)

    def test_duplicate_anchor_is_refused(self):
        source = self.ORIGINAL.replace(m.ORIGINAL, m.ORIGINAL + m.ORIGINAL)
        with self.assertRaisesRegex(ValueError, "navigation anchor ambiguous"):
            self.candidate(source)

    def test_double_publishing_is_refused(self):
        source = self.ORIGINAL.replace(
            b"<main>", b'<p>/moj-prop-intake/?format=html&amp;service=signals</p><main>')
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.candidate(source)

    def test_published_sources_are_pinned_and_no_filesystem_side_effects(self):
        self.assertEqual(m.PAGE, "moj-prop/signals/index.html")
        self.assertEqual(m.SOURCE_SHA256,
            "34b05a98ec6fa1eee9d8c340c7cc72a400e109aa712cc113da446f28661720b0")
        self.assertEqual(m.CANDIDATE_SHA256,
            "7ebd4931efb3594f334ee5867ab5974db4275742c11b277ae918b94dd32df4c6")
        self.assertNotIn("open(", m.generate_candidate.__code__.co_names)
        with self.assertRaises(TypeError):
            m.generate_candidate("not raw bytes")


if __name__ == "__main__":
    unittest.main()
