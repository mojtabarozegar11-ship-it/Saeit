"""Offline-only integrity contracts for the S-01 TRX source SHA probe."""
import unittest
from scripts.mpw_trx_live_source_guard_readonly_20261031 import (
    REFERENCE_SHA256, classify,
)


class SourceGuardTests(unittest.TestCase):
    def test_all_reference_bytes_still_block_public_release(self):
        result = classify(dict(REFERENCE_SHA256))
        self.assertTrue(result["source_identity_all_match"])
        self.assertFalse(result["release_permitted"])
        self.assertFalse(result["passenger_db_authority_verified"])
        self.assertEqual(result["observed_sha256"]["rate"], REFERENCE_SHA256["rate"])

    def test_one_rate_drift_fails_identity(self):
        values = dict(REFERENCE_SHA256)
        values["rate"] = "0" * 64
        result = classify(values)
        self.assertEqual(result["source_states"]["rate"], "SHA_DRIFT")
        self.assertFalse(result["source_identity_all_match"])

    def test_missing_guest_is_unsafe(self):
        values = dict(REFERENCE_SHA256)
        values["guest"] = None
        result = classify(values)
        self.assertEqual(result["source_states"]["guest"], "UNAVAILABLE_OR_UNSAFE")

    def test_invalid_hash_is_rejected(self):
        values = dict(REFERENCE_SHA256)
        values["web"] = "not-a-digest"
        self.assertEqual(classify(values)["source_states"]["web"], "INVALID_DIGEST")

    def test_extra_manifest_key_is_rejected(self):
        with self.assertRaises(ValueError):
            classify({**REFERENCE_SHA256, "unknown": "0" * 64})


if __name__ == "__main__":
    unittest.main()
