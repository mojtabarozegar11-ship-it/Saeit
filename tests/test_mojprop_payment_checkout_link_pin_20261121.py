"""Regression guards: never regenerate unsafe legacy TRX direct checkout link."""
from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from scripts import mojprop_payment_checkout_link_pin_20261121 as m


class RetiredUnsafeCheckoutLinkGeneratorTests(unittest.TestCase):
    ORIGINAL = b"<html><h1>Payment</h1><p>No customer invoice is open.</p></html>"

    def test_any_exact_old_source_is_always_refused(self):
        with patch.object(m, "SOURCE_SHA256", hashlib.sha256(self.ORIGINAL).hexdigest()):
            with self.assertRaisesRegex(RuntimeError, "legacy_checkout_link_generator_retired"):
                m.generate_candidate(self.ORIGINAL)

    def test_source_drift_and_type_errors_fail_before_any_output(self):
        with self.assertRaisesRegex(ValueError, "source drift"):
            m.generate_candidate(self.ORIGINAL)
        with self.assertRaises(TypeError):
            m.generate_candidate("not bytes")

    def test_previous_version_is_historical_not_a_new_payment_release(self):
        self.assertEqual(m.PAGE, "moj-prop/payment/index.html")
        self.assertEqual(
            m.SOURCE_SHA256,
            "1ff56cace9e52d2f6cd6a332bf3159cccbfc5ff7cf70a3c87b06ee497d1d1d7e"
        )
        self.assertEqual(
            m.HISTORICAL_UNSAFE_CANDIDATE_SHA256,
            "498e1ebe2260650c5170c3b577b06878dd3beb295c74f849344643f33ab6b59b"
        )
        self.assertNotIn('href="/mojprop-starter30-checkout/"', m.RETIRED_REASON)


if __name__ == "__main__":
    unittest.main()
