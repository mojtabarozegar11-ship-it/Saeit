"""Regression tests for the VPS-local autonomous repair/QC loop."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/factory_agri200_autonomous_closed_loop_20261023.py"
spec = importlib.util.spec_from_file_location("agri200_closed_loop", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ClosedLoopTests(unittest.TestCase):
    def fixture(self, temp):
        root = Path(temp) / "factory/private"
        area = root / "production-instructions"
        ops = Path(temp) / "factory/operations/production-instructions"
        area.mkdir(parents=True)
        (area / "stage-06").mkdir()
        ops.mkdir(parents=True)
        (area / "owner-agri200-p0-index.json").write_text(json.dumps({
            "topic_count": 200, "edition_goal_count": 400,
            "order_ids_ranked": ["WO-%08d" % i for i in range(1, 201)],
        }), encoding="utf-8")
        return root, ops, area

    def test_200_orders_or_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ops, area = self.fixture(temp)
            audit = mod.run_tick(root, ops, workers=False)
            self.assertEqual(audit["order_count"], 200)
            self.assertEqual(audit["after"]["stage6_strict_qc"], 0)
            self.assertFalse((area / "stage-06/autonomous-closed-loop-status.json").exists())
            index = area / "owner-agri200-p0-index.json"
            data = json.loads(index.read_text())
            data["order_ids_ranked"][100] = data["order_ids_ranked"][99]
            index.write_text(json.dumps(data))
            with self.assertRaisesRegex(RuntimeError, "P0_INDEX_INVALID"):
                mod.run_tick(root, ops, workers=False)

    def test_workers_in_order_with_rebuild_before_strict_qc(self):
        labels = [x[0] for x in mod.STAGES]
        self.assertEqual(labels, [
            "source_discovery", "source_validation", "design_and_prototype",
            "bilingual_manuscript", "technical_preflight", "source_specific_repair",
            "candidate_rebuild", "strict_independent_qc1000"])
        self.assertFalse(any("publish" in x for x in labels))

    def test_every_stage_runs_despite_an_earlier_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ops, area = self.fixture(temp)
            py = ops.parent.parent / ".venv/bin/python"
            py.parent.mkdir(parents=True)
            py.write_bytes(b"#!/bin/sh\nexit 0\n")
            py.chmod(0o700)
            for label, file, _, _ in mod.STAGES:
                (ops / file).write_text("# mock")
            seen = []
            def fake(command, **kwargs):
                seen.append(Path(command[2]).name)
                return SimpleNamespace(returncode=9 if len(seen) == 1 else 0)
            outcome = mod.run_tick(root, ops, workers=True, invoke=fake)
            self.assertEqual(len(seen), 8)
            self.assertEqual(outcome["worker_errors"], 1)
            self.assertEqual(outcome["stage_results"]["source_discovery"], "worker_exit_9")
            self.assertEqual(outcome["stage_results"]["strict_independent_qc1000"], "ok")
            self.assertFalse(outcome["public_sites_modified"])
            persisted = json.loads((area / "stage-06/autonomous-closed-loop-status.json").read_text())
            self.assertEqual(persisted["worker_errors"], 1)

    def test_rework_routes_cannot_forge_signatures(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ops, area = self.fixture(temp)
            inbox = area / "stage-05/strict-qc-rework"
            inbox.mkdir(parents=True)
            (inbox / "WO-00000001--r001.json").write_text(json.dumps({
                "must_resubmit_new_artifact_and_repeat_strict_qc": True,
                "critical_findings": [
                    "P0_DOWNLOADABLE_CANDIDATE_NOT_BUILT",
                    "P0_METHODS_ONLY_NOT_A_SUBJECT_SPECIFIC_SCIENTIFIC_PRODUCT",
                    "P0_INDEPENDENT_DOMAIN_EXPERT_NOT_SIGNED",
                    "P0_LEGAL_RIGHTS_AND_DISTRIBUTION_NOT_APPROVED",
                ]}))
            res = mod.qc_rework_facts(area)
            self.assertEqual(res["tickets"], 1)
            self.assertEqual(res["repair_route"]["technical_repackage_or_integrity_repair"], 1)
            self.assertEqual(res["repair_route"]["authentic_external_specialist_required"], 1)
            self.assertEqual(res["repair_route"]["distribution_rights_review_required"], 1)

    def test_bad_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ops, area = self.fixture(temp)
            lock = ops / ".agri200-autonomous-loop.lock"
            lock.symlink_to(area / "owner-agri200-p0-index.json")
            with self.assertRaisesRegex(RuntimeError, "UNSAFE_LOOP_LOCK"):
                mod.run_tick(root, ops, workers=False)

    def test_retry_same_revision_not_counted_as_product(self):
        with tempfile.TemporaryDirectory() as temp:
            root, ops, area = self.fixture(temp)
            inbox = area / "stage-05/completed-drafts"
            inbox.mkdir(parents=True)
            (inbox / "WO-00000001--r001.json").write_text("{}")
            one = mod.run_tick(root, ops, workers=False)
            self.assertEqual(one["after"]["new_revision_artifacts"], 0)
            (inbox / "WO-00000001--r002.json").write_text("{}")
            two = mod.run_tick(root, ops, workers=False)
            self.assertEqual(two["after"]["new_revision_artifacts"], 1)
            self.assertEqual(two["qc1000_approved_by_internal_workers"], 0)


if __name__ == "__main__":
    unittest.main()
