"""No rotation on rework, no fabricated reviews, and strictly one target."""
import importlib.util
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_strict_serial_fullcycle_v1.py"
spec = importlib.util.spec_from_file_location("strict_serial_fullcycle", SOURCE)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)
GOVERNANCE_SOURCE = SOURCE.with_name("factory_12_stage_governance.py")
governance_spec = importlib.util.spec_from_file_location("strict_serial_governance_test", GOVERNANCE_SOURCE)
governance_module = importlib.util.module_from_spec(governance_spec)
governance_spec.loader.exec_module(governance_module)


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

    def test_certified_stock_waits_for_independent_chatgpt_review_before_next_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            with patch.object(cycle, "certified_finished", return_value=True):
                result = cycle.tick(root, ops, runner=lambda *a, **kw: (_ for _ in ()).throw(
                    AssertionError("certified product must not rework")),
                    disk_usage=lambda _:Disk())
            self.assertTrue(result["certified_to_private_finished_goods"])
            self.assertEqual(result["processed_order"], "WO-00000601")
            self.assertFalse(result["independent_chatgpt_review_approved"])
            self.assertEqual(result["active_order_after_cycle"], "WO-00000601")
            self.assertEqual(result["stage_results"]["independent_chatgpt_review"],
                             "AWAITING_SIGNED_EXTERNAL_REVIEW")
            self.assertEqual(result["stages_executed"], 0)
            with patch.object(cycle, "certified_finished", return_value=True), patch.object(
                    cycle, "independently_reviewed", return_value=True):
                waiting_handoff = cycle.tick(root, ops, disk_usage=lambda _:Disk())
            self.assertEqual(waiting_handoff["active_order_after_cycle"], "WO-00000601")
            self.assertEqual(waiting_handoff["stage_results"]["private_store_handoff"],
                             "AWAITING_SIGNED_PRIVATE_STORE_RECEIPT")
            with patch.object(cycle, "certified_finished", return_value=True), patch.object(
                    cycle, "independently_reviewed", return_value=True), patch.object(
                    cycle, "store_handoff_verified", return_value=True):
                released = cycle.tick(root, ops, disk_usage=lambda _:Disk())
            self.assertEqual(released["active_order_after_cycle"], "WO-00000602")
            self.assertTrue(released["independent_chatgpt_review_approved"])
            self.assertTrue(released["private_store_handoff_verified"])
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

    def test_independent_review_requires_signed_receipt_and_exact_product_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ops = workspace(Path(folder))
            work_order = "WO-00000601"
            archive = root / "product-lifecycle/approved-finished-goods" / work_order
            archive.mkdir(parents=True)
            (archive / "product.zip").write_bytes(b"only-a-test-artifact")
            passport = root / "product-lifecycle/passports" / (work_order + ".json")
            passport.parent.mkdir(parents=True)
            passport.write_text(json.dumps({"producer_id":"factory-worker"}),encoding="utf8")
            audit = ops.parent / "independent-product-reviews" / work_order
            audit.mkdir(parents=True)
            report = audit / "report.json"
            report.write_text(json.dumps({"order":work_order,"decision":"approved",
                    "tests_performed":["independent recalculation"],"blocking_findings":[]}),
                    encoding="utf8")
            key = "ab" * 32
            store_key = "cd" * 32
            keys = root / "product-lifecycle/reviewer-keys.json"
            keys.write_text(json.dumps({"schema":"saeit.factory.reviewer-keys.v1",
                "reviewers":{"chatgpt-independent":key,
                             "store-handoff-operator":store_key}}),encoding="utf8")
            keys.chmod(0o600)

            def file_hash(path):
                return hashlib.sha256(path.read_bytes()).hexdigest()

            class ApprovedGovernance:
                @staticmethod
                def spec_path(_root, _order):
                    return passport

                @staticmethod
                def sha(path):
                    return file_hash(path)

                @staticmethod
                def verify_reviewer_signature(_root, review):
                    return governance_module.verify_reviewer_signature(_root, review)

            reviewer = ApprovedGovernance()
            review = {
                "schema":cycle.CHATGPT_REVIEW_SCHEMA,
                "order":work_order,
                "decision":"approved",
                "producer_id":"factory-worker",
                "reviewer_id":"chatgpt-independent",
                "reviewer_role":"ai_independent_technical_reviewer",
                "artifact_sha256":file_hash(archive / "product.zip"),
                "passport_sha256":file_hash(passport),
                "report_sha256":file_hash(report),
                "criteria":{name:"pass" for name in cycle.REVIEW_CRITERIA},
            }
            receipt = audit / "review.json"
            receipt.write_text(json.dumps(review),encoding="utf8")
            self.assertFalse(cycle.independently_reviewed(root, ops, work_order, reviewer))
            review["reviewer_signature"] = hmac.new(
                bytes.fromhex(key), governance_module.signed_review_message(review),
                hashlib.sha256).hexdigest()
            receipt.write_text(json.dumps(review),encoding="utf8")
            self.assertTrue(cycle.independently_reviewed(root, ops, work_order, reviewer))
            report.write_text(report.read_text() + "tampered",encoding="utf8")
            self.assertFalse(cycle.independently_reviewed(root, ops, work_order, reviewer))
            report.write_text(json.dumps({"order":work_order,"decision":"approved",
                "tests_performed":["independent recalculation"],"blocking_findings":[]}),
                encoding="utf8")
            (archive / "product.zip").write_bytes(b"changed-artifact")
            self.assertFalse(cycle.independently_reviewed(root, ops, work_order, reviewer))
            (archive / "product.zip").write_bytes(b"only-a-test-artifact")
            store_receipt = audit / "store-receipt.json"
            store_receipt.write_text(json.dumps({
                "order":work_order,"source_artifact_sha256":file_hash(archive / "product.zip"),
                "state":"received_private_in_store"}),encoding="utf8")
            handoff = {
                "schema":cycle.STORE_HANDOFF_SCHEMA,
                "order":work_order,
                "state":"received_private_in_store",
                "store_domain":"zomorodmelal.ir",
                "reviewer_id":"store-handoff-operator",
                "reviewer_role":"human_approver",
                "artifact_sha256":file_hash(archive / "product.zip"),
                "independent_review_sha256":file_hash(receipt),
                "store_receipt_sha256":file_hash(store_receipt),
                "public_enabled":False,
                "payment_recorded":False,
            }
            handoff_file = audit / "store-handoff.json"
            handoff_file.write_text(json.dumps(handoff),encoding="utf8")
            self.assertFalse(cycle.store_handoff_verified(root, ops, work_order, reviewer))
            handoff["reviewer_signature"] = hmac.new(
                bytes.fromhex(store_key), governance_module.signed_review_message(handoff),
                hashlib.sha256).hexdigest()
            handoff_file.write_text(json.dumps(handoff),encoding="utf8")
            self.assertTrue(cycle.store_handoff_verified(root, ops, work_order, reviewer))
            store_receipt.write_text(store_receipt.read_text()+"tampered",encoding="utf8")
            self.assertFalse(cycle.store_handoff_verified(root, ops, work_order, reviewer))

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
            with patch.object(cycle, "certified_finished", return_value=True), patch.object(
                    cycle, "independently_reviewed", return_value=True), patch.object(
                    cycle, "store_handoff_verified", return_value=True):
                done = cycle.tick(root,ops,disk_usage=lambda _:Disk())
            self.assertTrue(done["certified_to_private_finished_goods"])
            self.assertIsNone(done["active_order_after_cycle"])
            with patch.object(cycle, "certified_finished", return_value=True), patch.object(
                    cycle, "independently_reviewed", return_value=True), patch.object(
                    cycle, "store_handoff_verified", return_value=True):
                final=cycle.tick(root,ops,dry_run=True)
            self.assertTrue(final["all_complete"])


if __name__=="__main__":
    unittest.main()
