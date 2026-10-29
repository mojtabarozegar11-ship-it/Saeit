import argparse
import importlib.util
from pathlib import Path
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
    def test_sqlite_only_reads_header(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "db"
            p.write_bytes(b"SQLite format 3\\0" + b"x" * 40)
            self.assertTrue(mod.sqlite(p)["sqlite_header_valid"])
            self.assertEqual(mod.sqlite(p)["integrity_check"], "NOT_RUN")
    def test_no_deployment_claim(self):
        with tempfile.TemporaryDirectory() as d:
            a = argparse.Namespace(mount=[d], queue=[d], lock=[], sqlite=[], backup=[])
            x = mod.capture(a)
            self.assertFalse(x["deployment_authorized"])
            self.assertFalse(x["worker_running_verified"])
            self.assertEqual(x["offhost_backup_restored"], "NOT_VERIFIED")
    def test_queue_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a").write_text("a")
            self.assertEqual(mod.queue(d)["entries_at_least"], 1)
    def test_missing_command(self):
        self.assertEqual(mod.command(["/no-such-f01-command"])["state"], "UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
