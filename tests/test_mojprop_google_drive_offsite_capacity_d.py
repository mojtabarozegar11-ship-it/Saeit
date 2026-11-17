"""D-only no-I/O regression for real Plan1 cloud storage capacity screening."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from scripts.mojprop_google_drive_offsite_capacity_d import (
    GIB, MIB, OffsiteNotProven, OwnerDriveSnapshot
)

SHA = "84a3763f182e4d965fb484717c71630dbbcdcaf4"
NOW = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)


class TestOwnerDriveOffsiteGate(unittest.TestCase):
    def setUp(self):
        self.record = OwnerDriveSnapshot(
            source_commit=SHA,
            quota_checked_at=NOW.isoformat(),
            source_db_estimate_bytes=10 * GIB,
            source_app_bytes=1 * GIB,
            source_media_bytes=1 * GIB,
            google_drive_quota_free_bytes=28 * GIB,
            google_drive_quota_total_bytes=40 * GIB,
            reserve_bytes=1 * GIB,
            account_private=True,
            app_and_media_inventory_complete=True,
            quota_from_authenticated_owner_api=True,
            destination_not_cpanel_or_vps=True,
            owner_folder_access_verified=True,
            encrypted_before_upload=True,
            independent_key_recovery_verified=True,
            multipart_resumable_verified=True,
        )

    def check(self, record=None, expected=SHA, now=NOW):
        return (self.record if record is None else record).screen(
            expected_commit=expected, now=now)

    def denied(self, **changes):
        with self.assertRaises(OffsiteNotProven):
            self.check(replace(self.record, **changes))

    def test_positive_math_never_grants_release(self):
        result = self.check()
        self.assertEqual(result["minimum_screened_bytes"], 23 * GIB)
        self.assertFalse(result["quota_authenticated_by_this_process"])
        self.assertFalse(result["backup_uploaded_verified"])
        self.assertFalse(result["encrypted_backup_roundtrip_verified"])
        self.assertFalse(result["isolated_db_app_media_restore_verified"])
        self.assertFalse(result["lead_registration_authorized"])
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["payment_authorized"])

    def test_insufficient_quota(self):
        self.denied(google_drive_quota_free_bytes=22 * GIB)

    def test_quota_exact_boundary_is_math_screen_only(self):
        exact = replace(self.record, google_drive_quota_free_bytes=23 * GIB)
        self.assertTrue(self.check(exact)["capacity_math_screen_passed"])

    def test_quota_just_below_boundary(self):
        self.denied(google_drive_quota_free_bytes=23 * GIB - 1)

    def test_quota_exceeds_total(self):
        self.denied(google_drive_quota_free_bytes=41 * GIB)

    def test_unknown_free_quota(self):
        self.denied(google_drive_quota_free_bytes=None)

    def test_free_quota_zero(self):
        self.denied(google_drive_quota_free_bytes=0)

    def test_free_quota_boolean(self):
        self.denied(google_drive_quota_free_bytes=True)

    def test_free_quota_float(self):
        self.denied(google_drive_quota_free_bytes=28.0 * GIB)

    def test_unbounded_claimed_quota(self):
        self.denied(google_drive_quota_total_bytes=10**20)

    def test_db_size_unmeasured(self):
        self.denied(source_db_estimate_bytes=None)

    def test_db_size_zero(self):
        self.denied(source_db_estimate_bytes=0)

    def test_db_size_is_boolean(self):
        self.denied(source_db_estimate_bytes=True)

    def test_app_bytes_unmeasured(self):
        self.denied(source_app_bytes=None)

    def test_media_bytes_unmeasured(self):
        self.denied(source_media_bytes=None)

    def test_reserve_small(self):
        self.denied(reserve_bytes=511 * MIB)

    def test_reserve_boolean(self):
        self.denied(reserve_bytes=True)

    def test_source_commit_wrong(self):
        self.denied(source_commit="f" * 40)

    def test_expected_commit_wrong(self):
        with self.assertRaises(OffsiteNotProven):
            self.check(expected="f" * 40)

    def test_expected_commit_malformed(self):
        with self.assertRaises(OffsiteNotProven):
            self.check(expected="HEAD")

    def test_timestamp_missing(self):
        self.denied(quota_checked_at="")

    def test_timestamp_naive(self):
        self.denied(quota_checked_at="2026-11-17T02:00:00")

    def test_timestamp_future(self):
        self.denied(quota_checked_at=(NOW+timedelta(seconds=1)).isoformat())

    def test_timestamp_stale(self):
        self.denied(quota_checked_at=(NOW-timedelta(minutes=16)).isoformat())

    def test_timezone_aware_equivalent(self):
        iso=(NOW+timedelta(hours=3)).astimezone(timezone(timedelta(hours=3))).isoformat()
        record=replace(self.record, quota_checked_at=iso)
        self.assertTrue(self.check(record)["capacity_math_screen_passed"])

    def test_invalid_trusted_time(self):
        with self.assertRaises(OffsiteNotProven):
            self.check(now=datetime(2026,11,17,2,0))

    def test_account_not_private(self):
        self.denied(account_private=False)

    def test_unknown_privacy(self):
        self.denied(account_private=None)

    def test_incomplete_site_inventory(self):
        self.denied(app_and_media_inventory_complete=False)

    def test_unverified_provider_quota(self):
        self.denied(quota_from_authenticated_owner_api=False)

    def test_same_host_destination(self):
        self.denied(destination_not_cpanel_or_vps=False)

    def test_owner_folder_missing(self):
        self.denied(owner_folder_access_verified=False)

    def test_no_client_side_encryption(self):
        self.denied(encrypted_before_upload=False)

    def test_no_recoverable_private_key(self):
        self.denied(independent_key_recovery_verified=False)

    def test_non_resumable_large_upload(self):
        self.denied(multipart_resumable_verified=False)

    def test_boolean_flags_do_not_accept_string_true(self):
        self.denied(multipart_resumable_verified="true")

    def test_quota_boundary_cannot_grant_payment(self):
        record = replace(self.record, google_drive_quota_free_bytes=23 * GIB)
        self.assertFalse(self.check(record)["payment_authorized"])


if __name__ == "__main__":
    unittest.main()
