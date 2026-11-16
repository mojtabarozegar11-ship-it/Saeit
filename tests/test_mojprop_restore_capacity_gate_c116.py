"""Offline safety regression for Moj Prop independent restore capacity."""
import unittest
from dataclasses import replace

from scripts.mojprop_restore_capacity_gate import (
    CapacityNotProven,
    RestoreCapacity,
)


class CapacityGateTests(unittest.TestCase):
    def setUp(self):
        self.good = RestoreCapacity(
            live_database_bytes=9 * 1024**3,
            app_media_bytes=2 * 1024**3,
            destination_free_bytes=24 * 1024**3,
            headroom_bytes=2 * 1024**3,
            independent_destination=True,
            encrypted_private_storage=True,
            isolated_restore_supported=True,
        )

    def test_exact_capacity(self):
        self.assertEqual(self.good.verify(), 2 * 1024**3)

    def test_insufficient_capacity(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, destination_free_bytes=4 * 1024**3).verify()

    def test_equal_capacity_allowed_without_claiming_restore(self):
        required = self.good.required_bytes()
        self.assertEqual(replace(self.good, destination_free_bytes=required).verify(), 0)

    def test_no_independent_destination(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, independent_destination=False).verify()

    def test_no_encryption(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, encrypted_private_storage=False).verify()

    def test_no_isolated_restore(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, isolated_restore_supported=False).verify()

    def test_unknown_measurement(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, live_database_bytes=0).verify()

    def test_negative_headroom(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, headroom_bytes=-1).verify()

    def test_float_measurement(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, destination_free_bytes=24.0).verify()

    def test_boolean_disguised_as_bytes(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, app_media_bytes=True).verify()

    def test_unknown_control(self):
        with self.assertRaises(CapacityNotProven):
            replace(self.good, encrypted_private_storage=None).verify()


if __name__ == "__main__":
    unittest.main()
