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


if __name__ == "__main__":
    unittest.main()
