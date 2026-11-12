"""Synthetic filesystem metadata checks; never connect to a VPS."""

import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.mpw_vps_mount_capacity_readonly_20261105 import (
    GIB, decode_mount_path, inspect, parse_local_mounts,
)


MOUNTINFO = """\
101 100 8:1 / / rw - ext4 /dev/root rw
102 100 8:2 / /mnt/volume rw - xfs /dev/mapper/private rw
103 100 8:2 / /srv/bind rw - xfs /dev/mapper/private rw
104 100 8:3 / /mnt/volume\\040two rw - btrfs /dev/other rw
105 100 0:40 / /run rw - tmpfs tmpfs rw
106 100 0:41 / /mnt/network rw - nfs4 server:/data rw
"""


class MountCapacityTests(unittest.TestCase):
    def test_decodes_mountinfo_only_in_memory_and_filters_network(self):
        self.assertEqual(decode_mount_path("/mnt/my\\040volume"), "/mnt/my volume")
        mounts = parse_local_mounts(MOUNTINFO.splitlines())
        self.assertEqual(len(mounts), 4)
        self.assertIn(("/mnt/volume two", "btrfs"), mounts)
        self.assertNotIn(("/mnt/network", "nfs4"), mounts)

    def test_deduplicates_bind_mounts_and_reports_no_private_paths(self):
        devices = {
            "/home/operator": (1, 7 * GIB, True),
            "/": (1, 7 * GIB, True),
            "/mnt/volume": (2, 50 * GIB, True),
            "/srv/bind": (2, 50 * GIB, True),
            "/mnt/volume two": (3, 8 * GIB, False),
        }

        def fake_record(path):
            device, free_bytes, writable = devices[str(path)]
            return SimpleNamespace(st_dev=device), SimpleNamespace(
                f_bavail=free_bytes, f_frsize=1), writable

        def fake_stat(path):
            return fake_record(path)[0]

        def fake_statvfs(path):
            return fake_record(path)[1]

        def fake_access(path, mode):
            return fake_record(path)[2]

        with patch("builtins.open", return_value=io.StringIO(MOUNTINFO)), patch(
            "scripts.mpw_vps_mount_capacity_readonly_20261105.os.path.islink",
            return_value=False
        ), patch("scripts.mpw_vps_mount_capacity_readonly_20261105.os.stat", side_effect=fake_stat), patch(
            "scripts.mpw_vps_mount_capacity_readonly_20261105.os.statvfs",
            side_effect=fake_statvfs
        ), patch("scripts.mpw_vps_mount_capacity_readonly_20261105.os.access", side_effect=fake_access):
            record = inspect(home=Path("/home/operator"))
        self.assertEqual(record["home_free_bytes"], 7 * GIB)
        self.assertEqual(record["independent_local_device_count"], 2)
        self.assertEqual(record["independent_devices_meeting_size_floor"], 1)
        self.assertEqual(record["independent_devices_with_write_hint_and_size_floor"], 1)
        self.assertEqual(record["largest_independent_free_bytes"], 50 * GIB)
        self.assertTrue(record["inventory_complete"])
        self.assertFalse(record["release_permitted"])
        self.assertFalse(record["storage_isolation_approved"])
        printed = json.dumps(record)
        for private in ("/mnt/volume", "/srv/bind", "/home/operator", "/dev/other"):
            self.assertNotIn(private, printed)

    def test_no_accessible_alternative_fails_closed_without_approving_restore(self):
        mountinfo = "10 1 8:1 / / rw - ext4 /dev/root rw\n"
        with patch("builtins.open", return_value=io.StringIO(mountinfo)), patch(
            "scripts.mpw_vps_mount_capacity_readonly_20261105.os.path.islink", return_value=False
        ), patch("scripts.mpw_vps_mount_capacity_readonly_20261105.os.stat",
                 return_value=SimpleNamespace(st_dev=1)), patch(
            "scripts.mpw_vps_mount_capacity_readonly_20261105.os.statvfs",
            return_value=SimpleNamespace(f_bavail=6 * GIB, f_frsize=1)), patch(
            "scripts.mpw_vps_mount_capacity_readonly_20261105.os.access", return_value=True):
            record = inspect(home=Path("/home/operator"))
        self.assertEqual(record["independent_local_device_count"], 0)
        self.assertEqual(record["independent_devices_with_write_hint_and_size_floor"], 0)
        self.assertTrue(record["inventory_complete"])
        self.assertFalse(record["isolated_restore_performed"])


if __name__ == "__main__":
    unittest.main()
