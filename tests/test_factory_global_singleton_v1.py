"""Fail-closed regression coverage for the VPS-global factory lane claim."""
import fcntl
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).with_name("factory_global_singleton_v1.py")
spec = importlib.util.spec_from_file_location("factory_global_singleton_v1", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GlobalSingletonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "private"
        self.root.mkdir()

    def write_agri(self, *, active=None, complete=False, schema=True):
        p = self.root / "production-instructions/stage-06/strict-serial-active-v1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        d = {"active_order": active, "all_complete": complete}
        if schema:
            d["schema"] = "saeit.factory.strict-serial-fullcycle.v1"
        p.write_text(json.dumps(d), encoding="utf-8")
        return p

    def write_line41(self, *, active=None, waiting=None, schema=True):
        p = self.root / "quality-excellence/product-flow/active-slots/current.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        d = {"active": active if active is not None else [],
             "waiting": waiting if waiting is not None else []}
        if schema:
            d["schema"] = "saeit.factory.product-slots.v1"
        p.write_text(json.dumps(d), encoding="utf-8")
        return p

    def test_reservation_persists_between_ticks_and_is_idempotent(self):
        first = module.reserve_lane(self.root, "line41")
        second = module.reserve_lane(self.root, "line41")
        self.assertEqual(first, second)
        self.assertEqual(first["generation"], 1)
        self.assertEqual(first["owner"], "line41")
        with self.assertRaisesRegex(RuntimeError, "OTHER_LANE_RESERVED"):
            module.reserve_lane(self.root, "agri200")

    def test_live_agri_order_blocks_line41_without_claiming(self):
        self.write_agri(active="WO-00000001", complete=False)
        with self.assertRaisesRegex(RuntimeError, "AGRI200_ORDER_NOT_RELEASED"):
            module.reserve_lane(self.root, "line41")
        self.assertFalse((self.root / module.STATE_NAME).exists())

    def test_parked_incomplete_agri_order_remains_unchanged(self):
        path = self.write_agri(active=None, complete=False)
        before = path.read_bytes()
        state = module.reserve_lane(self.root, "line41")
        self.assertEqual(state["owner"], "line41")
        self.assertEqual(path.read_bytes(), before)

    def test_agri_order_missing_schema_fails_closed(self):
        self.write_agri(active=None, complete=False, schema=False)
        with self.assertRaisesRegex(RuntimeError, "AGRI200_STATE_UNTRUSTED"):
            module.reserve_lane(self.root, "line41")

    def test_agri_all_complete_must_be_boolean(self):
        path = self.write_agri(active=None, complete=False)
        data = json.loads(path.read_text())
        data["all_complete"] = "false"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(RuntimeError, "AGRI200_STATE_UNTRUSTED"):
            module.reserve_lane(self.root, "line41")

    def test_live_line41_slot_blocks_agri(self):
        self.write_line41(active=[{"recipe": "farm_enterprise_economics"}])
        with self.assertRaisesRegex(RuntimeError, "LINE41_PRODUCT_NOT_RELEASED"):
            module.reserve_lane(self.root, "agri200")

    def test_waiting_line41_slot_blocks_agri(self):
        self.write_line41(waiting=[{"recipe": "future_product"}])
        with self.assertRaisesRegex(RuntimeError, "LINE41_PRODUCT_NOT_RELEASED"):
            module.reserve_lane(self.root, "agri200")

    def test_untrusted_line41_schema_fails_closed(self):
        self.write_line41(schema=False)
        with self.assertRaisesRegex(RuntimeError, "LINE41_SLOT_UNKNOWN"):
            module.reserve_lane(self.root, "agri200")

    def test_bad_global_state_cannot_be_stolen(self):
        (self.root / module.STATE_NAME).write_text('{"owner":null}')
        with self.assertRaisesRegex(RuntimeError, "GLOBAL_STATE_INVALID"):
            module.reserve_lane(self.root, "line41")

    def test_process_lock_contention_fails_closed(self):
        lock = self.root / module.LOCK_NAME
        with lock.open("w") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "GLOBAL_RESERVATION_BUSY"):
                module.reserve_lane(self.root, "line41")

    def test_symlink_lock_is_rejected(self):
        dest = self.root / "other.lock"
        dest.write_text("")
        (self.root / module.LOCK_NAME).symlink_to(dest)
        with self.assertRaisesRegex(RuntimeError, "GLOBAL_LOCK_SYMLINK"):
            module.reserve_lane(self.root, "line41")


if __name__ == "__main__":
    unittest.main()
