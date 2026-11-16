"""Offline safety regressions for capacity admission; no host access."""
import unittest
from dataclasses import replace
from scripts.mojprop_restore_capacity_admission import (
    CapacityEvidence, CapacityAdmissionDenied, require_restore_capacity,
)


class CapacityGateTests(unittest.TestCase):
    def setUp(self):
        self.e = CapacityEvidence(
            source_database_bytes=9_000_000_000,
            source_application_bytes=500_000_000,
            source_media_bytes=500_000_000,
            destination_free_bytes=40_000_000_000,
            destination_total_bytes=50_000_000_000,
            independent_destination=True,
            encrypted_at_rest=True,
            owner_authorized=True,
            measured_at_epoch=10000,
            now_epoch=10001,
        )

    def test_accepts_independent_fresh_capacity(self):
        self.assertEqual(require_restore_capacity(self.e), 22_500_000_000)

    def test_rejects_missing_independent_mount(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, independent_destination=False))

    def test_rejects_unencrypted_destination(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, encrypted_at_rest=False))

    def test_rejects_no_authorization(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, owner_authorized=False))

    def test_rejects_known_insufficient_capacity(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_bytes=4_000_000_000))

    def test_rejects_stale_measurement(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, now_epoch=14000))

    def test_rejects_future_measurement(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, now_epoch=9999))

    def test_rejects_unknown_source(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, source_database_bytes=0))

    def test_rejects_negative_values(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_bytes=-1))

    def test_rejects_boolean_integer_confusion(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_bytes=True))

    def test_rejects_impossible_free_space(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_bytes=60_000_000_000))


if __name__ == "__main__":
    unittest.main()
