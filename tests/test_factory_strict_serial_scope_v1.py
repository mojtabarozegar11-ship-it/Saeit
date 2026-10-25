"""Shared-family cron protection must not silently disable unrelated orders."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/factory_strict_serial_scope_v1.py"
SPEC = importlib.util.spec_from_file_location("strict_scope_test", MODULE)
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)


class SharedScopeTests(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.root = Path(self.context.name)
        self.area = self.root / "production-instructions"
        self.area.mkdir()
        self.path = self.area / "owner-agri200-p0-index.json"
        self.ids = [f"WO-{601+i:08d}" for i in range(200)]
        self.path.write_text(json.dumps({"topic_count": 200,
                                         "order_ids_ranked": self.ids}))

    def test_exact_200_owned_orders_excluded_not_others(self):
        orders = scope.owner_agri200_ids(self.root)
        self.assertEqual(len(orders), 200)
        self.assertIn("WO-00000601", orders)
        self.assertNotIn("WO-00000001", orders)

    def test_corrupt_scope_fails_closed(self):
        self.path.write_text('{"topic_count":200,"order_ids_ranked":[]}')
        with self.assertRaisesRegex(RuntimeError, "EXCLUSION_INDEX_INVALID"):
            scope.owner_agri200_ids(self.root)

    def test_symlink_scope_fails_closed(self):
        original = self.area / "authentic.json"
        self.path.rename(original)
        self.path.symlink_to(original)
        with self.assertRaisesRegex(RuntimeError, "EXCLUSION_INDEX_UNSAFE"):
            scope.owner_agri200_ids(self.root)


if __name__ == "__main__":
    unittest.main()
