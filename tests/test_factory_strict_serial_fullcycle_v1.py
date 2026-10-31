"""No rotation on rework, no fabricated reviews, and strictly one target."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
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


def accepted_handoff(root, order, cycle_id="B-01"):
    finished = root / "product-lifecycle/approved-finished-goods" / order
    receiver = root / "product-lifecycle/hourly-cycle-handoffs" / cycle_id / order
    finished.mkdir(parents=True, exist_ok=True)
    receiver.mkdir(parents=True, exist_ok=True)
    data = b"synthetic-private-artifact-for-unit-test"
    (finished / "product.zip").write_bytes(data)
    (receiver / "product.zip").write_bytes(data)
    (receiver / "receipt.json").write_text(json.dumps({
        "schema": cycle.HANDOFF_SCHEMA,
        "order": order,
        "receiver_cycle": cycle_id,
        "status": "accepted_by_receiver",
        "artifact_sha256": hashlib.sha256(data).hexdigest(),
        "acceptance_evidence": "receiver acceptance record in private handoff inbox",
    }), encoding="utf8")
    key_dir = root / "test-trusted-receiver-keys"
    key_dir.mkdir(exist_ok=True, mode=0o700)
    secret = key_dir / (cycle_id + ".test-private.pem")
    public = key_dir / (cycle_id + ".pem")
    subprocess.run(["openssl", "ecparam", "-name", "prime256v1", "-genkey",
                    "-noout", "-out", str(secret)], check=True, capture_output=True)
    subprocess.run(["openssl", "pkey", "-in", str(secret), "-pubout",
                    "-out", str(public)], check=True, capture_output=True)
    sign_receipt(receiver, secret)
    return receiver


def sign_receipt(receiver, secret):
    subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(secret),
                    "-out", str(receiver / "receipt.sig"),
                    str(receiver / "receipt.json")], check=True, capture_output=True)


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
            "0 3 * * * /opt/unrelated-backup\n")
        cycle.verify_cron_partition(valid)
        with self.assertRaisesRegex(RuntimeError, "COMPETING_OWNER_WORKER"):
            cycle.verify_cron_partition(valid +
                "* * * * * /ops/legacy # SAEIT_AGRI200_AUTONOMOUS_CLOSED_LOOP_V1\n")
        with self.assertRaisesRegex(RuntimeError, "COMPETING_SHARED_FACTORY_WORKER"):
            cycle.verify_cron_partition(valid +
                "* * * * * /ops/stage2-research-serial.py --exclude-owner-agri200 # "
                "SAEIT_FACTORY_STAGE2_RESEARCH_V1\n")
        with self.assertRaisesRegex(RuntimeError, "UNKNOWN_FACTORY_CRON"):
            cycle.verify_cron_partition(valid +
                "* * * * * python /opt/factory/another_product.py\n")
        with self.assertRaisesRegex(RuntimeError, "SCOPE_FLAG_MISSING"):
            cycle.verify_cron_partition(valid.replace("--require-scheduler-scope", ""))
        with self.assertRaisesRegex(RuntimeError, "COMMAND_INVALID"):
            cycle.verify_cron_partition(valid.replace("strict-serial-fullcycle-v1.py",
                                                       "unrelated.py"))

    def test_one_product_holds_across_rework_cycles(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            calls = []

            def run(argv, **kwargs):
                calls.append(tuple(argv))
                return Successful()

            for _ in range(3):
                result = cycle.tick(root, ops, runner=run, disk_usage=lambda _:Disk(),
                                    monotonic=lambda:0)
                self.assertEqual(result["processed_order"], "WO-00000601")
                self.assertEqual(result["active_order_after_cycle"], "WO-00000601")
                self.assertFalse(result["certified_to_private_finished_goods"])
                self.assertEqual(result["stages_executed"], len(cycle.STAGES))
                self.assertEqual(result["publications"], 0)
            self.assertEqual(len(calls), len(cycle.STAGES) * 3)
            for args in calls:
                self.assertTrue(any("WO-00000601" in value for value in args))
                self.assertFalse(any("WO-00000602" in value for value in args))
                self.assertTrue(("--only-order-id" in args) ^ ("--only-order-file" in args))
            state = json.loads((root / "production-instructions/stage-06/strict-serial-active-v1.json")
                               .read_text())
            self.assertEqual(state["ticks"], 3)
            self.assertEqual(state["active_order"], "WO-00000601")

    def test_low_disk_prevents_all_workers_including_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            calls = []
            result = cycle.tick(root, ops, runner=lambda argv, **k: (
                calls.append(argv) or Successful()), disk_usage=lambda _:SmallDisk(),
                monotonic=lambda:0)
            self.assertEqual(result["stages_executed"], 0)
            self.assertEqual(calls, [])
            self.assertTrue(result["storage_hold"])
            self.assertTrue(all(status == "STORAGE_RESERVE_HOLD"
                                for status in result["stage_results"].values()))
            self.assertFalse(result["certified_to_private_finished_goods"])

    def test_mid_cycle_disk_drop_blocks_later_workers(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            calls = []
            checks = [Disk(), Disk(), SmallDisk()]
            def disk_usage(_):
                return checks.pop(0) if checks else SmallDisk()
            def runner(argv, **kwargs):
                calls.append(argv)
                return Successful()
            result = cycle.tick(root, ops, runner=runner,
                                disk_usage=disk_usage, monotonic=lambda:0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(result["stages_executed"], 1)
            self.assertEqual(result["stage_results"]["source_discovery"],
                             "STORAGE_RESERVE_HOLD")
            self.assertTrue(result["storage_hold"])
            self.assertFalse(result["certified_to_private_finished_goods"])
            self.assertEqual(result["active_order_after_cycle"], "WO-00000601")

    def test_certification_alone_never_starts_second_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            with patch.object(cycle, "certified_finished", return_value=True):
                result = cycle.tick(root, ops, runner=lambda *a, **kw: (_ for _ in ()).throw(
                    AssertionError("certified product must not rework")),
                    disk_usage=lambda _:Disk())
            self.assertTrue(result["certified_to_private_finished_goods"])
            self.assertEqual(result["processed_order"], "WO-00000601")
            self.assertEqual(result["active_order_after_cycle"], "WO-00000601")
            self.assertFalse(result["handoff_accepted"])
            self.assertEqual(result["stages_executed"], 0)
            accepted_handoff(root, "WO-00000601")
            with (patch.object(cycle, "certified_finished", return_value=True),
                  patch.object(cycle, "TRUST_ROOT", root / "test-trusted-receiver-keys")):
                delivered = cycle.tick(root, ops, disk_usage=lambda _:Disk())
            self.assertTrue(delivered["handoff_accepted"])
            self.assertEqual(delivered["active_order_after_cycle"], "WO-00000602")
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

    def test_handoff_requires_matching_copy_hash_and_receiver_ack(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            receipt_dir = accepted_handoff(root, "WO-00000601")
            receipt_file = receipt_dir / "receipt.json"
            receipt = json.loads(receipt_file.read_text())
            receipt["artifact_sha256"] = "0" * 64
            receipt_file.write_text(json.dumps(receipt))
            with patch.object(cycle, "TRUST_ROOT", root / "test-trusted-receiver-keys"):
                self.assertFalse(cycle.handoff_accepted(root, "WO-00000601"))
                with patch.object(cycle, "certified_finished", return_value=True):
                    held = cycle.tick(root, ops, disk_usage=lambda _:Disk())
                self.assertEqual(held["active_order_after_cycle"], "WO-00000601")
                receipt["artifact_sha256"] = hashlib.sha256(
                    (receipt_dir / "product.zip").read_bytes()).hexdigest()
                receipt["acceptance_evidence"] = "tampered receiver claim"
                receipt_file.write_text(json.dumps(receipt))
                # A correct SHA in a tampered receipt is still not an acceptance.
                self.assertFalse(cycle.handoff_accepted(root, "WO-00000601"))
                sign_receipt(receipt_dir, root / "test-trusted-receiver-keys/B-01.test-private.pem")
                self.assertTrue(cycle.handoff_accepted(root, "WO-00000601"))

    def test_unsigned_and_untrusted_receipts_cannot_unlock_next_product(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            receiver = accepted_handoff(root, "WO-00000601")
            with (patch.object(cycle, "TRUST_ROOT", root / "test-trusted-receiver-keys"),
                  patch.object(cycle, "certified_finished", return_value=True)):
                (receiver / "receipt.sig").unlink()
                self.assertFalse(cycle.handoff_accepted(root, "WO-00000601"))
                held = cycle.tick(root, ops, disk_usage=lambda _:Disk())
                self.assertEqual(held["active_order_after_cycle"], "WO-00000601")
                sign_receipt(receiver, root / "test-trusted-receiver-keys/B-01.test-private.pem")
                (root / "test-trusted-receiver-keys/B-01.pem").unlink()
                self.assertFalse(cycle.handoff_accepted(root, "WO-00000601"))

    def test_budget_does_not_create_false_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            times = iter([0] + [100] * len(cycle.STAGES))
            result = cycle.tick(root, ops, runner=lambda *a, **kw:Successful(),
                                disk_usage=lambda _:Disk(), monotonic=lambda:next(times))
            self.assertEqual(result["stages_executed"], 0)
            self.assertEqual(result["active_order_after_cycle"], "WO-00000601")
            self.assertEqual(result["stage_results"]["strict_qc"], "DEFERRED_TO_NEXT_MINUTE")

    def test_full_index_preflight_rejects_missing_later_orders(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            area = root / "production-instructions"
            for pos in (1, 2, 200):
                ident = "WO-%08d" % (600 + pos)
                (area / "orders" / (ident + ".json")).write_text(json.dumps({
                    "id": ident, "status": "issued", "fingerprint": "a"*64,
                    "origin": "owner_requested_agri200_p0",
                    "source_product_id": "AGRI-%03d" % pos,
                }), encoding="utf8")
            with self.assertRaisesRegex(
                    RuntimeError, "STRICT_SERIAL_COMPLETE_INDEX_MISSING_OR_INVALID"):
                cycle.tick(root, ops, dry_run=True, verify_complete_intake=True,
                           disk_usage=lambda _:Disk())
            self.assertFalse((ops / ".strict-serial-fullcycle.lock").exists())

    def test_full_index_preflight_accepts_only_real_agri_cohort(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            area = root / "production-instructions"
            for pos in range(1, 201):
                ident = "WO-%08d" % (600 + pos)
                (area / "orders" / (ident + ".json")).write_text(json.dumps({
                    "id": ident, "status": "issued", "fingerprint": "a"*64,
                    "origin": "owner_requested_agri200_p0",
                    "source_product_id": "AGRI-%03d" % pos,
                }), encoding="utf8")
            okay = cycle.tick(root, ops, dry_run=True,
                              verify_complete_intake=True,
                              disk_usage=lambda _:Disk())
            self.assertEqual(okay["active_order"], "WO-00000601")
            changed = area / "orders" / "WO-00000602.json"
            value = json.loads(changed.read_text(encoding="utf8"))
            value["origin"] = "site-topic-snapshot"
            changed.write_text(json.dumps(value), encoding="utf8")
            with self.assertRaisesRegex(RuntimeError,
                                        "STRICT_SERIAL_COMPLETE_INDEX_COHORT_MISMATCH"):
                cycle.tick(root, ops, dry_run=True,
                           verify_complete_intake=True,
                           disk_usage=lambda _:Disk())
            with self.assertRaisesRegex(RuntimeError,
                                        "STRICT_SERIAL_COMPLETE_INDEX_ONLY_DRY_RUN"):
                cycle.tick(root, ops, verify_complete_intake=True,
                           disk_usage=lambda _:Disk())

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
            accepted_handoff(root, "WO-00000800")
            with (patch.object(cycle, "certified_finished", return_value=True),
                  patch.object(cycle, "TRUST_ROOT", root / "test-trusted-receiver-keys")):
                done = cycle.tick(root,ops,disk_usage=lambda _:Disk())
            self.assertTrue(done["certified_to_private_finished_goods"])
            self.assertIsNone(done["active_order_after_cycle"])
            with (patch.object(cycle, "certified_finished", return_value=True),
                  patch.object(cycle, "handoff_accepted", return_value=True)):
                final=cycle.tick(root,ops,dry_run=True)
            self.assertTrue(final["all_complete"])


if __name__=="__main__":
    unittest.main()
