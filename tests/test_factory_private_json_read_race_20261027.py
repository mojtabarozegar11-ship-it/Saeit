"""Regression: transient private-state filesystem failures must not crash the factory."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_vps_product_cycle.py"
spec = importlib.util.spec_from_file_location("factory_private_json_read_race", SCRIPT)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


class PrivateJsonFailClosedTests(unittest.TestCase):
    def test_stat_permission_error_is_safe_absence(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            path.write_text('{"schema":"safe"}', encoding="utf8")
            original_stat = Path.stat
            def guarded_stat(self, *args, **kwargs):
                if self == path:
                    raise PermissionError("transient private filesystem access")
                return original_stat(self, *args, **kwargs)
            with mock.patch.object(Path, "stat", guarded_stat):
                self.assertIsNone(cycle._read_private_json(path))

    def test_oversized_and_nonobject_state_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            path.write_text("x" * 2_000_001, encoding="utf8")
            self.assertIsNone(cycle._read_private_json(path))
            path.write_text('["not", "a", "dict"]', encoding="utf8")
            self.assertIsNone(cycle._read_private_json(path))
            path.write_text('{"schema":"safe"}', encoding="utf8")
            self.assertEqual(cycle._read_private_json(path), {"schema":"safe"})



    def test_growth_after_stat_is_rejected_before_unbounded_allocation(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            oversized = Path(root) / "oversized.json"
            path.write_text('{"schema":"safe"}', encoding="utf8")
            oversized.write_bytes(b"x" * 2_000_001)
            original_open = os.open
            def raced_open(target, flags, *args, **kwargs):
                if Path(target) == path:
                    # Simulate a different, larger inode opened after preflight.
                    return original_open(oversized, flags, *args, **kwargs)
                return original_open(target, flags, *args, **kwargs)
            with mock.patch.object(os, "open", raced_open):
                self.assertIsNone(cycle._read_private_json(path))

    def test_symlink_swap_after_preflight_is_not_followed(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            sensitive = Path(root) / "sensitive.json"
            path.write_text('{"schema":"safe"}', encoding="utf8")
            sensitive.write_text('{"private":"must-not-follow"}', encoding="utf8")
            original_open = os.open
            def swapped_open(target, flags, *args, **kwargs):
                if Path(target) == path:
                    path.unlink()
                    path.symlink_to(sensitive)
                return original_open(target, flags, *args, **kwargs)
            with mock.patch.object(os, "open", swapped_open):
                self.assertIsNone(cycle._read_private_json(path))
            self.assertEqual(sensitive.read_text(encoding="utf8"), '{"private":"must-not-follow"}')

    def test_fifo_private_state_is_rejected_without_blocking(self):
        import os
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO requires POSIX")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "state.json"
            os.mkfifo(path)
            self.assertIsNone(cycle._read_private_json(path))

if __name__ == "__main__":
    unittest.main()
