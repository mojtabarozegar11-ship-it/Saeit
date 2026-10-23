"""Tests for the delegated private factory supervisor (no external services)."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "factory_delegated_internal_autonomy_20261023.py"
spec = importlib.util.spec_from_file_location("delegated_factory", SOURCE)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)

GOOD_WORKER = """
import argparse
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--factory-private', required=True)
parser.add_argument('--stage34-worker')
parser.add_argument('--stage5-worker')
parser.add_argument('--stage6-worker')
parser.add_argument('--batch')
args=parser.parse_args()
directory=Path(args.factory_private)/'production-instructions'
name=Path(__file__).name
mapping={
    'stage34-autonomous-handoff.py': ('stage-03/receipts','stage-04/receipts'),
    'stage5-evidence-workbook.py': ('stage-05/completed-drafts',),
    'stage6-preflight-rework.py': ('stage-06/technical-preflight',),
    'stage5-substantive-rework.py': ('stage-05/substantive-revision-manifests',),
}
for target in mapping[name]:
    folder=directory/target
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'WO-001.json').write_text('{"verified":true}',encoding='utf-8')
print('VERIFIED_PRIVATE_MOCK_STAGE=' + name)
"""


class OwnerDelegatedAutonomy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.private = self.base / "private"
        (self.private / "production-instructions").mkdir(parents=True)
        self.ops = self.base / "operations"
        self.ops.mkdir()
        for _, name in agent.STEPS:
            (self.ops / name).write_text(GOOD_WORKER, encoding="utf-8")

    def cycle(self):
        return agent.execute(self.private, self.ops, sys.executable, batch=2, timeout=10)

    def test_runs_four_real_subprocess_steps_without_owner_prompt(self):
        out = self.cycle()
        self.assertEqual("advanced", out["status"])
        self.assertEqual(4, len(out["workers"]))
        self.assertTrue(all(x["passed"] for x in out["workers"]))
        self.assertEqual(5, sum(out["new_private_receipts"].values()))
        self.assertFalse(
            out["operating_authority"]["repeat_owner_confirmation_required_for_internal_work"])
        self.assertFalse(out["independent_specialist_review_auto_certified"])
        self.assertFalse(out["commercial_quality1000_certified"])
        self.assertFalse(out["public_distribution_authorized"])
        self.assertFalse(out["websites_modified"])
        persisted = json.loads((
            self.private / "production-instructions" / "delegated-internal-autonomy-status.json"
        ).read_text())
        self.assertEqual(persisted["verified_receipt_counts"], out["verified_receipt_counts"])

    def test_second_cycle_is_idempotent_and_does_not_invent_new_products(self):
        self.cycle()
        after = self.cycle()
        self.assertEqual("idle", after["status"])
        self.assertEqual(0, sum(after["new_private_receipts"].values()))

    def test_worker_failure_is_visible_and_does_not_count_as_certification(self):
        (self.ops / "stage6-preflight-rework.py").write_text(
            "raise SystemExit(9)\n", encoding="utf-8")
        out = self.cycle()
        self.assertEqual("degraded", out["status"])
        self.assertEqual(["stage6"], out["failed_workers"])
        self.assertEqual("repair_failed_worker_and_retry", out["next_action"])
        self.assertFalse(out["independent_specialist_review_auto_certified"])

    def test_refuses_symlink_worker(self):
        worker = self.ops / "stage5-evidence-workbook.py"
        worker.unlink()
        worker.symlink_to(self.ops / "stage34-autonomous-handoff.py")
        with self.assertRaisesRegex(RuntimeError, "AUTONOMY_UNSAFE_EXECUTABLE"):
            self.cycle()

    def test_resource_limits(self):
        with self.assertRaisesRegex(RuntimeError, "AUTONOMY_BOUNDED_RESOURCES_REQUIRED"):
            agent.execute(self.private, self.ops, sys.executable, batch=500)

    def test_symlink_status_is_rejected(self):
        target = self.private / "production-instructions" / "delegated-internal-autonomy-status.json"
        other = self.base / "outside.json"
        other.write_text("DO_NOT_TOUCH", encoding="utf-8")
        target.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, "AUTONOMY_UNSAFE_STATUS_PATH"):
            self.cycle()
        self.assertEqual("DO_NOT_TOUCH", other.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
