"""Read-only byte-exact host-template patch regression; no deployment."""
from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch
from scripts import mojtaba_bot_live_portal_security_candidate_20261121 as m


class LiveMojtabaBotPortalCandidateTests(unittest.TestCase):
    SOURCE = (
        b'<html><head><title>Central Bot</title></head><body>\n'
        + m.OLD_GATE
        + b'<section aria-label="free proposal">\n'
        + m.ORIGINAL_CTA
        + b'</section><script nonce="{{ nonce }}">protectedChat()</script>\n'
        + b'</body></html>'
    )

    def _candidate(self, original):
        candidate = original.replace(m.OLD_GATE, m.SAFE_GATE, 1)
        candidate = candidate.replace(m.ORIGINAL_CTA,
                                      m.ORIGINAL_CTA + m.SIGNALS_CTA, 1)
        with patch.object(m, "ORIGINAL_SHA256", hashlib.sha256(original).hexdigest()), \
             patch.object(m, "CANDIDATE_SHA256", hashlib.sha256(candidate).hexdigest()):
            return m.generate_candidate(original)

    def test_only_safe_gate_and_one_free_signals_link_change(self):
        candidate = self._candidate(self.SOURCE)
        self.assertNotIn(b'/mojprop-starter30-checkout/', candidate)
        self.assertEqual(candidate.count(b'service=signals'), 1)
        self.assertIn(b'Do not send TRX.', candidate)
        self.assertIn(b'not guaranteed', candidate)
        self.assertIn(b'nonce="{{ nonce }}"', candidate)
        self.assertIn(m.ORIGINAL_CTA, candidate)
        restored = candidate.replace(m.ORIGINAL_CTA + m.SIGNALS_CTA,
                                     m.ORIGINAL_CTA, 1).replace(
                                         m.SAFE_GATE, m.OLD_GATE, 1)
        self.assertEqual(restored, self.SOURCE)

    def test_source_digest_drift_denied(self):
        with self.assertRaisesRegex(ValueError, 'source SHA256 drift'):
            m.generate_candidate(self.SOURCE)

    def test_duplicate_gate_or_free_anchor_denied(self):
        for data in (self.SOURCE + m.OLD_GATE, self.SOURCE + m.ORIGINAL_CTA):
            with self.subTest(data=data[-30:]):
                with self.assertRaisesRegex(ValueError, 'ambiguous'):
                    self._candidate(data)

    def test_already_present_signal_link_denied(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self._candidate(self.SOURCE + b'<a href="?service=signals">x</a>')

    def test_other_legacy_link_denied(self):
        with self.assertRaisesRegex(ValueError, 'checkout anchor mismatch'):
            self._candidate(self.SOURCE + b'href="/mojprop-starter30-checkout/"')

    def test_no_string_input_and_exact_release_digest_pins(self):
        with self.assertRaises(TypeError):
            m.generate_candidate("not bytes")
        self.assertEqual(m.TEMPLATE, 'templates/core/mojtaba_bot_portal.html')
        self.assertEqual(m.ORIGINAL_SHA256,
                         'c39817f7ac714b69be2920c4d02537096b0a4f18cf35b8bda2de754e36ae56ca')
        self.assertEqual(m.CANDIDATE_SHA256,
                         '17b341a62338964f83ef36e8bbcbedac1feaf8e179f73df151bae746cca67ad5')


if __name__ == '__main__':
    unittest.main()
