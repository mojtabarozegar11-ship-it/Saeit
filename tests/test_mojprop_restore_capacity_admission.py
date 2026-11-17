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
            tenant_quota_free_bytes=40_000_000_000,
            tenant_quota_total_bytes=50_000_000_000,
            destination_free_inodes=500_000,
            required_restore_inodes=100_000,
            tenant_quota_free_inodes=500_000,
            tenant_quota_total_inodes=1_000_000,
        )

    def test_rejects_missing_quota_evidence(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_bytes=None))

    def test_rejects_quota_smaller_than_filesystem(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_bytes=4_000_000_000))

    def test_rejects_impossible_tenant_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_bytes=60_000_000_000))

    def test_rejects_unknown_inode_budget(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_inodes=None))

    def test_rejects_insufficient_inode_budget(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_inodes=99_999))

    def test_rejects_zero_required_inodes(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, required_restore_inodes=0))

    def test_rejects_boolean_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_bytes=True))

    def test_rejects_boolean_inodes(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, destination_free_inodes=True))

    def test_rejects_unknown_tenant_inode_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_inodes=None))

    def test_rejects_unknown_total_tenant_inode_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_total_inodes=None))

    def test_rejects_tenant_inode_shortage_even_with_filesystem_inodes(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_inodes=99_999))

    def test_rejects_impossible_tenant_free_inode_count(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_inodes=1_000_001))

    def test_rejects_zero_tenant_inode_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_total_inodes=0,
                                              tenant_quota_free_inodes=0))

    def test_rejects_bool_tenant_inode_quota(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, tenant_quota_free_inodes=True))

    def test_rejects_zero_application_archive_estimate(self):
        with self.assertRaises(CapacityAdmissionDenied):
            require_restore_capacity(replace(self.e, source_application_bytes=0))

    def test_accepts_truly_empty_media_directory_if_inventory_attested(self):
        e = replace(self.e, source_media_bytes=0)
        self.assertEqual(require_restore_capacity(e), 21_375_000_000)

    def test_accepts_exact_equal_inode_capacity_without_guessing(self):
        e = replace(self.e, destination_free_inodes=100_000,
                    tenant_quota_free_inodes=100_000)
        self.assertEqual(require_restore_capacity(e), 22_500_000_000)

    def test_rejects_empty_destination_and_quota(self):
        for change in (
            {"destination_total_bytes": 0, "destination_free_bytes": 0},
            {"tenant_quota_total_bytes": 0, "tenant_quota_free_bytes": 0},
        ):
            with self.subTest(change=change):
                with self.assertRaises(CapacityAdmissionDenied):
                    require_restore_capacity(replace(self.e, **change))

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
