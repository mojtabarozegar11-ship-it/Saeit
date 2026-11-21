"""Pure regression for exact host-byte pinned Starter30 catalog CTA; no deployment."""
import hashlib
import unittest
from unittest.mock import patch

from scripts import mojprop_catalog_current_live_offer_patch_20261121 as m


class ExactCurrentCatalogPatchTests(unittest.TestCase):
    ORIGINAL = (
        b'<html lang="en"><head><style>p{color:gold}</style></head>'
        b'<body><main>'
        b'<section class="hero">Four research services.</section>'
        b'<section class="process"><p>Manual research review.</p></section>'
        b'</main><script defer src="/mpw-measure/tracker.js"></script></body></html>'
    )

    def verified(self, original):
        with patch.object(m, "SOURCE_SHA256", hashlib.sha256(original).hexdigest()):
            return m.generate_candidate(original)

    def test_injects_exact_one_simulated_offer_with_safe_free_terms_cta(self):
        result = self.verified(self.ORIGINAL)
        self.assertEqual(result.count(b'id="starter30-offer"'), 1)
        self.assertEqual(result.count(b'/moj-prop/starter-30-trx/'), 1)
        self.assertNotIn(b'/mojprop-starter30-checkout/', result)
        self.assertEqual(result.count(b'/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx'), 1)
        self.assertIn(b'30 TRX', result)
        self.assertIn(b'60-day simulated challenge', result)
        self.assertIn(b'virtual USD 1,000', result)
        self.assertIn(b'no customer trading capital', result.lower())
        self.assertIn(b'actual company-funded payout execution has not been independently established', result)

    def test_preserves_all_other_bytes_and_existing_consent_script(self):
        result = self.verified(self.ORIGINAL)
        self.assertEqual(result.replace(m.NEW_OFFER, b"", 1), self.ORIGINAL)
        self.assertEqual(result.count(b'/mpw-measure/tracker.js'), 1)
        self.assertIn(b'<style>p{color:gold}</style>', result)
        self.assertIn(b'<script defer src="/mpw-measure/tracker.js"></script>', result)

    def test_drift_is_rejected_before_any_change(self):
        with self.assertRaisesRegex(ValueError, "source drift"):
            m.generate_candidate(self.ORIGINAL)
        self.assertEqual(m.SOURCE_SHA256, "33275fc11f578bbf8b6021535504866a7483e40bb840da98c9d5ac0e35455842")

    def test_rejects_already_released_offer_and_duplicate_anchor(self):
        with self.assertRaises(ValueError):
            self.verified(self.ORIGINAL.replace(b'<section class="process">', b'<section class="process"><section class="process">'))
        with self.assertRaisesRegex(ValueError, "already linked"):
            self.verified(self.ORIGINAL.replace(b'Four research services.', b'<a href="/mojprop-starter30-checkout/">Buy</a>'))

    def test_rejects_telemetry_loss_or_mutation(self):
        with self.assertRaisesRegex(ValueError, "telemetry"):
            self.verified(self.ORIGINAL.replace(b'/mpw-measure/tracker.js', b'/changed-analytics.js'))

    def test_requires_bytes(self):
        with self.assertRaises(TypeError):
            m.generate_candidate("not bytes")

    def test_no_other_site_or_wallet_in_new_markup(self):
        self.assertIn(b'Request written Starter30 terms without payment', m.NEW_OFFER)
        self.assertNotIn(b'/mojprop-starter30-checkout/', m.NEW_OFFER)
        self.assertNotIn(b'<form', m.NEW_OFFER)
        self.assertNotIn(b'<script', m.NEW_OFFER)
        self.assertNotIn(b'TH', m.NEW_OFFER)
        self.assertEqual(m.PAGE, "moj-prop/catalog/index.html")


if __name__ == "__main__":
    unittest.main()
