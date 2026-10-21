"""Verify F28 private warehouse intake uses real artifacts and rejects shortcuts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import factory_f28_private_build_cycle_20261021 as build
from scripts import factory_f28_private_warehouse_intake_20261021 as intake

ROOT = Path(__file__).resolve().parents[1]
MAKER = ROOT / "scripts" / "factory_product_maker.py"
WAREHOUSE = ROOT / "scripts" / "factory_production_warehouse.py"
SOURCE = ROOT / "product_recipes" / "greenhouse_crop_margin"


class PrivateCentralIntakeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="f28-central-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate"
        self.factory = self.root / "central"
        self.factory.mkdir(mode=0o700)
        evidence = build.build_cycle(SOURCE, MAKER, self.candidate, revision="test-commit")
        self.assertEqual(evidence["status"], "private_technical_candidate_verified")

    def run_intake(self):
        return intake.accept(self.candidate, self.factory, WAREHOUSE)

    def test_contended_warehouse_lock_waits_and_eventually_acquires(self):
        with tempfile.TemporaryFile() as handle:
            with mock.patch.object(intake.fcntl, "flock",
                    side_effect=[BlockingIOError(), None]) as lock, \
                 mock.patch.object(intake.time, "monotonic",
                    side_effect=[10.0, 10.2]), \
                 mock.patch.object(intake.time, "sleep") as pause:
                intake.acquire_warehouse_lock(handle, wait_seconds=2)
            self.assertEqual(lock.call_count, 2)
            pause.assert_called_once_with(0.5)
            self.assertTrue(all(c.args[1] == (intake.fcntl.LOCK_EX | intake.fcntl.LOCK_NB)
                                for c in lock.call_args_list))

    def test_contended_warehouse_lock_times_out_without_force_unlock(self):
        with tempfile.TemporaryFile() as handle:
            with mock.patch.object(intake.fcntl, "flock",
                    side_effect=BlockingIOError()) as lock, \
                 mock.patch.object(intake.time, "monotonic",
                    side_effect=[0.0, 2.0]), \
                 mock.patch.object(intake.time, "sleep") as pause:
                with self.assertRaisesRegex(RuntimeError, "WAREHOUSE_LOCKED_RETRY"):
                    intake.acquire_warehouse_lock(handle, wait_seconds=1)
            lock.assert_called_once()
            pause.assert_not_called()

    def test_real_build_stocked_immutable_and_1000_held(self):
        receipt = self.run_intake()
        self.assertEqual(receipt["action"], "stocked")
        self.assertTrue(receipt["stock_version_verified"])
        self.assertFalse(receipt["professional_quality_1000_approved"])
        self.assertFalse(receipt["public_listing_enabled"])
        version = (self.factory / "production-warehouse" / "finished"
                   / intake.RECIPE / receipt["source_sha256"])
        self.assertTrue((version / "product.zip").is_file())
        manifest = json.loads((version / "warehouse_manifest.json").read_text())
        self.assertFalse(manifest["commercial_release"])
        self.assertEqual(manifest["site_transfer_state"], "not_transferred")
        review = (self.factory / "quality-excellence" / "private-intake-review"
                  / intake.RECIPE / receipt["source_sha256"] / "pending.json")
        doc = json.loads(review.read_text())
        self.assertEqual(doc["rubric_maximum"], 1000)
        self.assertIsNone(doc["verified_total_score"])
        self.assertTrue(all(v["verified_score"] is None for v in doc["rubric"].values()))
        register = json.loads((self.factory / "production-warehouse" / "stock-register.json").read_text())
        self.assertEqual(register["finished_goods_versions"], 1)

    def test_repeated_receipt_is_idempotent(self):
        self.assertEqual(self.run_intake()["action"], "stocked")
        self.assertEqual(self.run_intake()["action"], "already_stocked")

    def test_corrupted_package_is_rejected_without_stock(self):
        artifact = (self.candidate / "private-stock" / intake.RECIPE
                    / (intake.RECIPE + "-internal-qa.zip"))
        artifact.write_bytes(artifact.read_bytes() + b"corruption")
        with self.assertRaisesRegex(RuntimeError, "MISMATCH"):
            self.run_intake()
        self.assertFalse((self.factory / "production-warehouse" / "finished").exists())

    def test_fake_professional_approval_is_rejected(self):
        path = self.candidate / "private-cycle-receipt.json"
        doc = json.loads(path.read_text())
        doc["independent_professional_quality_1000_passed"] = True
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(RuntimeError, "EVIDENCE_MISSING"):
            self.run_intake()

    def test_active_factory_rework_hold_blocks_intake(self):
        ledger = self.factory / "qa-rework" / intake.RECIPE
        ledger.mkdir(parents=True)
        (ledger / "ledger.json").write_text(json.dumps({
            "schema": "saeit.factory.qa-rework.v1",
            "current_status": "needs_rework"}))
        with self.assertRaisesRegex(RuntimeError, "REWORK_HOLD"):
            self.run_intake()
        self.assertFalse((self.factory / "production-warehouse" / "finished").exists())


if __name__ == "__main__":
    unittest.main()
