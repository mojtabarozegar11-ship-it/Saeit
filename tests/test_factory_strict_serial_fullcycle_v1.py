"""Fair one-product-per-tick rework, no fabricated reviews or cross-order writes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_strict_serial_fullcycle_v1.py"
spec = importlib.util.spec_from_file_location("strict_serial_fullcycle", SOURCE)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


def workspace(parent):
    root = parent / "factory-runtime/private/autonomous-product-cycle"
    ops = parent / "factory-runtime/operations/production-instructions"
    area = root / "production-instructions"
    (area / "stage-06").mkdir(parents=True)
    ops.mkdir(parents=True)
    python = parent / "factory-runtime/.venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("only-a-test-placeholder")
    python.chmod(0o700)
    ids = ["WO-%08d" % i for i in range(601, 801)]
    (area / "owner-agri200-p0-index.json").write_text(
        json.dumps({"topic_count":200, "order_ids_ranked":ids}), encoding="utf8")
    (area / "orders").mkdir()
    for work_id in (ids[0], ids[1], ids[-1]):
        (area / "orders" / (work_id + ".json")).write_text(json.dumps({
            "id":work_id,"status":"issued","fingerprint":"a"*64}))
    for _, file, _, _ in cycle.STAGES:
        (ops / file).write_text("synthetic-test-worker", encoding="utf8")
    (ops / "agri200-strict-qc-catalog.json").write_text("{}")
    return root, ops


class Disk:
    free = 4 * 1024**3


class SmallDisk:
    free = 1024**3


class Successful:
    returncode = 0


class StrictSerialTests(unittest.TestCase):
    def test_live_scheduler_guard_rejects_competing_bulk_worker(self):
        valid = (
            "* * * * * /ops/strict-serial-fullcycle-v1.py --require-scheduler-scope # "
            + cycle.SERIAL_MARKER + "\n"
            "* * * * * /ops/stage2-research-serial.py --exclude-owner-agri200 # "
            "SAEIT_FACTORY_STAGE2_RESEARCH_V1\n")
        cycle.verify_cron_partition(valid)
        with self.assertRaisesRegex(RuntimeError, "COMPETING_OWNER_WORKER"):
            cycle.verify_cron_partition(valid +
                "* * * * * /ops/legacy # SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1\n")
        with self.assertRaisesRegex(RuntimeError, "UNPARTITIONED"):
            cycle.verify_cron_partition(valid.replace("--exclude-owner-agri200", ""))

    def test_rework_rotates_fairly_without_false_certification(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            calls = []

            def run(argv, **kwargs):
                calls.append(tuple(argv))
                return Successful()

            first = cycle.tick(root, ops, runner=run, disk_usage=lambda _:Disk(),
                               monotonic=lambda:0)
            second = cycle.tick(root, ops, runner=run, disk_usage=lambda _:Disk(),
                                monotonic=lambda:0)
            self.assertEqual(first["processed_order"], "WO-00000601")
            self.assertEqual(first["active_order_after_cycle"], "WO-00000602")
            self.assertEqual(second["processed_order"], "WO-00000602")
            self.assertEqual(second["active_order_after_cycle"], "WO-00000603")
            for result in (first, second):
                self.assertEqual(result["decision"], "RETURN_TO_PRODUCTION")
                self.assertEqual(result["required_next_version"], "AUTHENTIC_REWORK_VERSION")
                self.assertFalse(result["certified_to_private_finished_goods"])
                self.assertEqual(result["stages_executed"], len(cycle.STAGES))
                self.assertEqual(result["publications"], 0)
            self.assertEqual(len(calls), len(cycle.STAGES) * 2)
            for args in calls[:len(cycle.STAGES)]:
                self.assertTrue(any("WO-00000601" in value for value in args))
                self.assertFalse(any("WO-00000602" in value for value in args))
            for args in calls[len(cycle.STAGES):]:
                self.assertTrue(any("WO-00000602" in value for value in args))
                self.assertFalse(any("WO-00000601" in value for value in args))
            state = json.loads((root / "production-instructions/stage-06/strict-serial-active-v1.json")
                               .read_text())
            self.assertEqual(state["active_order"], "WO-00000603")
            self.assertEqual(state["last_decision"], "RETURN_TO_PRODUCTION")

    def test_last_order_wraps_to_unfinished_first_instead_of_deadlocking(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            state = root / "production-instructions/stage-06/strict-serial-active-v1.json"
            state.write_text(json.dumps({"schema":cycle.SCHEMA,
                                         "active_order":"WO-00000800", "index":199,
                                         "ticks":19}))
            def verified(_root, order, _governance):
                return order != "WO-00000601"
            with patch.object(cycle, "certified_finished", side_effect=verified):
                result = cycle.tick(root, ops, runner=lambda *a, **kw:Successful(),
                                    disk_usage=lambda _:Disk(), monotonic=lambda:0)
            self.assertEqual(result["processed_order"], "WO-00000800")
            self.assertEqual(result["decision"], "CERTIFIED_AND_EXIT")
            self.assertEqual(result["active_order_after_cycle"], "WO-00000601")
            self.assertFalse(json.loads(state.read_text())["all_complete"])

    def test_low_disk_only_triages_selected_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            calls = []
            result = cycle.tick(root, ops, runner=lambda argv, **k: (
                calls.append(argv) or Successful()), disk_usage=lambda _:SmallDisk(),
                monotonic=lambda:0)
            self.assertEqual(result["stages_executed"], 1)
            self.assertEqual(len(calls), 1)
            self.assertIn("--only-order-file", calls[0])
            self.assertTrue(result["storage_hold"])
            self.assertEqual(result["stage_results"]["strict_qc"], "STORAGE_RESERVE_HOLD")

    def test_certified_real_stock_is_only_path_to_next_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            with patch.object(cycle, "certified_finished",
                              side_effect=lambda _root, order, _gov: order == "WO-00000601"):
                result = cycle.tick(root, ops, runner=lambda *a, **kw: (_ for _ in ()).throw(
                    AssertionError("certified product must not rework")),
                    disk_usage=lambda _:Disk())
            self.assertTrue(result["certified_to_private_finished_goods"])
            self.assertEqual(result["processed_order"], "WO-00000601")
            self.assertEqual(result["active_order_after_cycle"], "WO-00000602")
            self.assertEqual(result["stages_executed"], 0)
            # An arbitrary claim without real governance does not release.
            forged = root / "product-lifecycle/approved-finished-goods/WO-00000602"
            forged.mkdir(parents=True)
            (forged / "receipt.json").write_text('{"quality1000_approved":true}')
            (forged / "product.zip").write_bytes(b"NOT_A_REAL_ZIP")
            self.assertFalse(cycle.certified_finished(root, "WO-00000602", None))
            result = cycle.tick(root, ops, runner=lambda *a, **kw:Successful(),
                                disk_usage=lambda _:Disk(),monotonic=lambda:0)
            self.assertEqual(result["processed_order"], "WO-00000602")
            self.assertFalse(result["certified_to_private_finished_goods"])

    def test_budget_does_not_create_false_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            times = iter([0] + [100] * len(cycle.STAGES))
            result = cycle.tick(root, ops, runner=lambda *a, **kw:Successful(),
                                disk_usage=lambda _:Disk(), monotonic=lambda:next(times))
            self.assertEqual(result["stages_executed"], 0)
            self.assertEqual(result["active_order_after_cycle"], "WO-00000602")
            self.assertEqual(result["decision"], "RETURN_TO_PRODUCTION")
            self.assertEqual(result["stage_results"]["strict_qc"], "DEFERRED_TO_NEXT_MINUTE")

    def test_dry_run_never_writes_private_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            result = cycle.tick(root,ops,dry_run=True,disk_usage=lambda _:Disk())
            self.assertEqual(result["active_order"],"WO-00000601")
            self.assertFalse((ops / ".strict-serial-fullcycle.lock").exists())
            self.assertFalse((root / "production-instructions/stage-06/strict-serial-active-v1.json").exists())

    def test_bad_cursor_does_not_select_another_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            state=root / "production-instructions/stage-06/strict-serial-active-v1.json"
            state.write_text(json.dumps({"schema":cycle.SCHEMA, "active_order":"WO-00000602",
                                         "index":0,"ticks":1}))
            with self.assertRaises(RuntimeError):
                cycle.tick(root,ops,dry_run=True)

    def test_last_product_certification_finishes_queue_instead_of_wrapping(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            state=root / "production-instructions/stage-06/strict-serial-active-v1.json"
            state.write_text(json.dumps({"schema":cycle.SCHEMA,
                                         "active_order":"WO-00000800", "index":199,
                                         "ticks":19}))
            with patch.object(cycle, "certified_finished", return_value=True):
                done = cycle.tick(root,ops,disk_usage=lambda _:Disk())
            self.assertTrue(done["certified_to_private_finished_goods"])
            self.assertIsNone(done["active_order_after_cycle"])
            with patch.object(cycle, "certified_finished", return_value=True):
                final=cycle.tick(root,ops,dry_run=True)
            self.assertTrue(final["all_complete"])


    def test_missing_intake_returns_precise_rework_and_rotates(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            state = root / "production-instructions/stage-06/strict-serial-active-v1.json"
            state.write_text(json.dumps({"schema":cycle.SCHEMA,
                                         "active_order":"WO-00000603", "index":2, "ticks":0}))
            def forbidden(*args, **kwargs):
                raise AssertionError("invalid intake must never run a producer")
            result = cycle.tick(root, ops, runner=forbidden,
                                disk_usage=lambda _:Disk(), monotonic=lambda:0)
            self.assertEqual(result["processed_order"], "WO-00000603")
            self.assertEqual(result["decision"], "RETURN_TO_PRODUCTION")
            self.assertEqual(result["rework_stage_owner"], "intake_integrity")
            self.assertIn("UNSAFE_OR_MISSING_SERIAL_EVIDENCE", result["intake_blocker"])
            self.assertEqual(result["stage_results"]["strict_qc"], "SKIPPED_INVALID_INTAKE")
            self.assertEqual(result["stages_executed"], 0)
            self.assertEqual(result["active_order_after_cycle"], "WO-00000604")
            self.assertFalse(result["certified_to_private_finished_goods"])
            persisted = json.loads(state.read_text())
            self.assertEqual(persisted["active_order"], "WO-00000604")
            self.assertEqual(persisted["last_decision"], "RETURN_TO_PRODUCTION")
            self.assertEqual(persisted["intake_blocker"], result["intake_blocker"])

    def test_corrupt_intake_does_not_block_next_valid_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            first_path = root / "production-instructions/orders/WO-00000601.json"
            first_path.write_text('{"id":"WO-00000601","status":"issued","fingerprint":"INVALID"}')
            calls = []
            def run(argv, **kwargs):
                calls.append(argv)
                return Successful()
            first = cycle.tick(root, ops, runner=run,
                               disk_usage=lambda _:Disk(), monotonic=lambda:0)
            self.assertEqual(first["decision"], "RETURN_TO_PRODUCTION")
            self.assertIn("STAGE1_WORK_ORDER_INVALID", first["intake_blocker"])
            self.assertEqual(first["active_order_after_cycle"], "WO-00000602")
            self.assertEqual(calls, [])
            second = cycle.tick(root, ops, runner=run,
                                disk_usage=lambda _:Disk(), monotonic=lambda:0)
            self.assertEqual(second["processed_order"], "WO-00000602")
            self.assertEqual(second["stages_executed"], len(cycle.STAGES))
            self.assertEqual(len(calls), len(cycle.STAGES))
            self.assertFalse(second["certified_to_private_finished_goods"])

    def test_dry_run_missing_intake_remains_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            (root / "production-instructions/orders/WO-00000601.json").unlink()
            result = cycle.tick(root, ops, dry_run=True, disk_usage=lambda _:Disk())
            self.assertIsNotNone(result["intake_blocker"])
            self.assertFalse(result["certified"])
            self.assertFalse((ops / ".strict-serial-fullcycle.lock").exists())
            self.assertFalse((root / "production-instructions/stage-06/strict-serial-active-v1.json").exists())


if __name__=="__main__":
    unittest.main()
