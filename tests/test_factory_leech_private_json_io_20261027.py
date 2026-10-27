"""Private leech author provenance inputs must fail closed on I/O races."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_leech_free_offline_original_author_20261025.py"
spec = importlib.util.spec_from_file_location("leech_private_json_io_guard", SCRIPT)
author = importlib.util.module_from_spec(spec)
spec.loader.exec_module(author)

class LeechPrivateJsonIOTests(unittest.TestCase):
    def test_stat_permission_error_is_a_private_provenance_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "provenance.json"
            path.write_text('{"order_id":"WO-26102501"}', encoding="utf8")
            original_stat = Path.stat
            def blocked(self, *args, **kwargs):
                if self == path:
                    raise PermissionError("transient read denial")
                return original_stat(self, *args, **kwargs)
            with mock.patch.object(Path, "stat", blocked):
                with self.assertRaisesRegex(RuntimeError, "LEECH_ZERO_COST_UNREADABLE_PRIVATE_JSON"):
                    author.safe_json(path)

    def test_valid_private_json_still_loads_and_oversized_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "provenance.json"
            path.write_text('{"order_id":"WO-26102501"}', encoding="utf8")
            self.assertEqual(author.safe_json(path)["order_id"], "WO-26102501")
            path.write_text("x" * 300001, encoding="utf8")
            with self.assertRaisesRegex(RuntimeError, "LEECH_ZERO_COST_MISSING_OR_UNSAFE_JSON"):
                author.safe_json(path)


    def test_file_growth_between_stat_and_read_is_bounded(self):
        import io
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "provenance.json"
            path.write_text('{"order_id":"WO-26102501"}', encoding="utf8")
            original_open = Path.open
            def grown_open(self, *args, **kwargs):
                if self == path and args and args[0] == "rb":
                    return io.BytesIO(b"x" * 41)
                return original_open(self, *args, **kwargs)
            with mock.patch.object(Path, "open", grown_open):
                with self.assertRaisesRegex(RuntimeError, "LEECH_ZERO_COST_MISSING_OR_UNSAFE_JSON"):
                    author.safe_json(path, max_bytes=40)

if __name__ == "__main__":
    unittest.main()
