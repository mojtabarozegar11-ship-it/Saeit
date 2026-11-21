"""Fail-closed tests for exact-byte payment-page checkout navigation generator."""
from __future__ import annotations
import hashlib
import unittest
from unittest.mock import patch

from scripts import mojprop_payment_checkout_link_pin_20261121 as m


class PaymentCheckoutLinkPatchTest(unittest.TestCase):
    ORIGINAL = (
        b'<html><head><style>.nav{display:flex}</style></head><body>'
        b'<h1>Payment disclosure</h1>'
        + m.PROTECTED_DISCLOSURES[0]
        + m.PROTECTED_DISCLOSURES[1]
        + m.ORIGINAL_LINKS
        + b'<a href="/moj-prop/rules/">All risk rules</a></p>'
        + b'<script defer src="/mpw-measure/tracker.js"></script>'
        + b'</body></html>'
    )

    def patched(self, blob):
        candidate = blob.replace(m.ORIGINAL_LINKS, m.UPDATED_LINKS, 1)
        with patch.object(m, 'SOURCE_SHA256', hashlib.sha256(blob).hexdigest()):
            with patch.object(m, 'CANDIDATE_SHA256', hashlib.sha256(candidate).hexdigest()):
                return m.generate_candidate(blob)

    def test_exact_change_only(self):
        patched = self.patched(self.ORIGINAL)
        self.assertEqual(patched.replace(m.UPDATED_LINKS, m.ORIGINAL_LINKS, 1), self.ORIGINAL)
        self.assertEqual(patched.count(b'/mojprop-starter30-checkout/'), 1)
        self.assertEqual(patched.count(b'/mpw-measure/tracker.js'), 1)
        self.assertIn(b'Review the official 30 TRX checkout form', patched)

    def test_fails_closed_on_drift(self):
        with self.assertRaisesRegex(ValueError, 'source drift'):
            m.generate_candidate(self.ORIGINAL)

    def test_does_not_repeat_existing_link(self):
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.patched(self.ORIGINAL.replace(b'Payment disclosure',
                b'Payment disclosure /mojprop-starter30-checkout/'))

    def test_guards_disclosures(self):
        for phrase in m.PROTECTED_DISCLOSURES:
            with self.subTest(phrase=phrase):
                with self.assertRaisesRegex(ValueError, 'protected disclosure'):
                    self.patched(self.ORIGINAL.replace(phrase, b''))

    def test_guards_duplicate_anchor(self):
        with self.assertRaisesRegex(ValueError, 'anchor changed'):
            self.patched(self.ORIGINAL.replace(m.ORIGINAL_LINKS, m.ORIGINAL_LINKS * 2))

    def test_rejects_text_not_bytes(self):
        with self.assertRaises(TypeError):
            m.generate_candidate('not byte content')

    def test_published_sha_pinned(self):
        self.assertEqual(m.PAGE, 'moj-prop/payment/index.html')
        self.assertEqual(m.SOURCE_SHA256,
            '1ff56cace9e52d2f6cd6a332bf3159cccbfc5ff7cf70a3c87b06ee497d1d1d7e')
        self.assertEqual(m.CANDIDATE_SHA256,
            '498e1ebe2260650c5170c3b577b06878dd3beb295c74f849344643f33ab6b59b')


if __name__ == '__main__':
    unittest.main()
