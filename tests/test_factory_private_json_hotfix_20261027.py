"""Regression tests for the narrowly scoped, reversible VPS state-reader repair."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_private_json_hotfix_20261027.py"
spec = importlib.util.spec_from_file_location("factory_private_json_hotfix", SCRIPT)
hotfix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hotfix)

class JsonReaderHotfixTests(unittest.TestCase):
    def fixture(self):
        return "import json\nfrom pathlib import Path\n\n" + hotfix.OLD + "\ndef other_factory_method():\n    return 101\n"

    def test_exact_old_block_changes_and_other_source_unchanged(self):
        old = self.fixture()
        new, changed = hotfix.transform(old)
        self.assertTrue(changed)
        self.assertEqual(new, old.replace(hotfix.OLD, hotfix.NEW))
        self.assertIn("def other_factory_method():\n    return 101", new)
        ast.parse(new)

    def test_second_run_is_idempotent(self):
        new, changed = hotfix.transform(self.fixture())
        self.assertTrue(changed)
        again, changed = hotfix.transform(new)
        self.assertFalse(changed)
        self.assertEqual(again, new)

    def test_unknown_drift_rejected_without_weakened_gate(self):
        old = self.fixture()
        with self.assertRaisesRegex(ValueError, "REVIEWED_SOURCE_BLOCK_NOT_EXACT"):
            hotfix.transform(old.replace("2_000_000", "999999999"))
        with self.assertRaises(ValueError):
            hotfix.transform(old + hotfix.NEW)
        with self.assertRaises(ValueError):
            hotfix.transform(old + hotfix.OLD)

    def test_applied_reader_handles_transient_stat_error(self):
        new, changed = hotfix.transform(self.fixture())
        namespace = {}
        exec(compile(new, "<reviewed-private-reader>", "exec"), namespace)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            path.write_text('{"ok":true}', encoding="utf8")
            self.assertEqual(namespace["_read_private_json"](path), {"ok": True})
            prior = Path.stat
            def unavailable(self, *a, **kw):
                if self == path:
                    raise PermissionError("transient")
                return prior(self, *a, **kw)
            with mock.patch.object(Path, "stat", unavailable):
                self.assertIsNone(namespace["_read_private_json"](path))

    def test_invalid_run_id_rejected_before_host_access(self):
        with self.assertRaises(ValueError):
            hotfix.repair("../untrusted", apply=True)

if __name__ == "__main__":
    unittest.main()
