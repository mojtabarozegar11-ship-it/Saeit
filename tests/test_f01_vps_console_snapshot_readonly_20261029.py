import argparse
import importlib.util
from pathlib import Path
from unittest import mock
import tempfile
import unittest

src = Path(__file__).resolve().parents[1] / "scripts/f01_vps_console_snapshot_readonly_20261029.py"
spec = importlib.util.spec_from_file_location("f01_snapshot", src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SnapshotTests(unittest.TestCase):
    def test_missing_is_not_healthy(self):
        self.assertEqual(mod.stat_path("/unlikely/nonexistent/f01/20261029")["state"], "MISSING")
    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "f"
            p.write_text("x")
            q = Path(d) / "l"
            q.symlink_to(p)
            self.assertEqual(mod.stat_path(q)["state"], "SYMLINK_NOT_FOLLOWED")
    def test_linked_ancestor_is_not_followed_for_filesystem_or_queue(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "actual"
            base.mkdir()
            (base / "private").mkdir()
            link = Path(d) / "alias"
            link.symlink_to(base, target_is_directory=True)
            self.assertEqual(mod.stat_path(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")
            self.assertEqual(mod.mount(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")
            self.assertEqual(mod.queue(link / "private")["state"], "SYMLINK_NOT_FOLLOWED")

    def test_sqlite_only_reads_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db"
            p.write_bytes(b"SQLite format 3\0" + b"x" * 40)
            self.assertTrue(mod.sqlite(p)["sqlite_header_valid"])
            self.assertEqual(mod.sqlite(p)["integrity_check"], "NOT_RUN")
    def test_sqlite_linked_parent_is_never_followed(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d) / "private"
            private.mkdir()
            (private / "db").write_bytes(b"SQLite format 3\0" + b"x" * 40)
            alias = Path(d) / "alias"
            alias.symlink_to(private, target_is_directory=True)
            result = mod.sqlite(alias / "db")
            self.assertEqual(result["state"], "UNAVAILABLE")
            self.assertNotIn("sqlite_header_valid", result)

    def test_sqlite_fifo_is_rejected_without_blocking(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            fifo = Path(d) / "pipe"
            os.mkfifo(fifo)
            result = mod.sqlite(fifo)
            self.assertEqual(result["state"], "UNAVAILABLE")

    def test_sqlite_uses_open_descriptor_not_prior_stat_path(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "db"
            db.write_bytes(b"SQLite format 3\0" + b"x" * 40)
            with mock.patch.object(mod, "stat_path", side_effect=AssertionError("unsafe pre-open stat")):
                result = mod.sqlite(db)
            self.assertEqual(result["state"], "PRESENT")
            self.assertTrue(result["sqlite_header_valid"])
            self.assertEqual(result["bytes"], 56)

    def test_no_deployment_claim(self):
        with tempfile.TemporaryDirectory() as d:
            a = argparse.Namespace(mount=[d], queue=[d], lock=[], sqlite=[], backup=[])
            x = mod.capture(a)
            self.assertFalse(x["deployment_authorized"])
            self.assertFalse(x["worker_running_verified"])
            self.assertEqual(x["offhost_backup_restored"], "NOT_VERIFIED")
    def test_private_path_labels_are_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            a = argparse.Namespace(mount=[d], queue=[d], lock=[d], sqlite=[d], backup=[d])
            x = mod.capture(a)
            self.assertTrue(x["path_labels_redacted"])
            for category in ("filesystem", "queue", "locks", "sqlite", "backup"):
                self.assertEqual(list(x[category]), ["target_1"])
                self.assertNotIn(d, str(list(x[category])))

    def test_lsblk_mountpoint_never_requested_or_emitted(self):
        calls = []
        def fake_command(argv):
            calls.append(argv)
            if argv[0] == "lsblk":
                return {"state": "OBSERVED", "output": (
                    '{"blockdevices":[{"name":"vda","size":"42",'
                    '"mountpoint":"/PRIVATE/DO_NOT_LOG",'
                    '"children":[{"name":"vda1","mountpoints":["/secret"]}]}]}')}
            return {"state": "UNAVAILABLE"}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mod, "command", side_effect=fake_command):
            args = argparse.Namespace(mount=[d], queue=[], lock=[], sqlite=[], backup=[])
            result = mod.capture(args)
        self.assertNotIn("MOUNTPOINT", str(calls[0]))
        self.assertNotIn("/PRIVATE", str(result))
        self.assertNotIn("/secret", str(result))
        self.assertEqual(result["block_topology"]["devices"]["blockdevices"][0]["name"], "vda")

    def test_sqlite_leaf_symlink_swap_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "private"
            real.write_bytes(b"SQLite format 3\0" + b"data")
            link = Path(d) / "db"
            link.symlink_to(real)
            # Simulate a symlink swap after metadata validation.
            with mock.patch.object(mod, "stat_path", return_value={"state":"PRESENT", "is_file":True}):
                observed = mod.sqlite(link)
            self.assertEqual(observed["state"], "UNAVAILABLE")
            self.assertFalse(observed.get("sqlite_header_valid", False))

    def test_queue_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a").write_text("a")
            self.assertEqual(mod.queue(d)["entries_at_least"], 1)
    def test_queue_uses_directory_fd_not_preopen_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a").write_text("a")
            with mock.patch.object(mod, "stat_path", side_effect=AssertionError("unsafe path stat")):
                result = mod.queue(d)
            self.assertEqual(result["state"], "OBSERVED")
            self.assertEqual(result["entries_at_least"], 1)

    def test_queue_symlinked_parent_refuses_enumeration(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d) / "private"
            private.mkdir()
            (private / "queue").mkdir()
            alias = Path(d) / "alias"
            alias.symlink_to(private, target_is_directory=True)
            result = mod.queue(alias / "queue")
            self.assertEqual(result["state"], "SYMLINK_NOT_FOLLOWED")

    def test_missing_command(self):
        self.assertEqual(mod.command(["/no-such-f01-command"])["state"], "UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
