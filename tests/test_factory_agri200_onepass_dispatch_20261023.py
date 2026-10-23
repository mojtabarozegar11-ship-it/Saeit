"""Release safety and deterministic dispatch tests for the 200 P0 orders."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/factory_agri200_onepass_dispatch_20261023.py"
spec = importlib.util.spec_from_file_location("agri200_onepass", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OnePassTests(unittest.TestCase):
    def test_exact_200_orders_and_audit_never_promotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            area = root / "production-instructions"
            ops = Path(directory) / "operations/production-instructions"
            area.mkdir(parents=True)
            ops.mkdir(parents=True)
            orders = ["WO-%08d" % i for i in range(1, 201)]
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": orders}), encoding="utf8")
            result = module.dispatch(root, ops, run_workers=False)
            self.assertEqual(result["before"]["stage2_researched"], 0)
            self.assertEqual(result["after"]["internal_orders"], 200)
            self.assertEqual(result["after"]["planned_language_editions"], 400)
            self.assertFalse(result["after"]["storefront_release_verified"])
            self.assertFalse(result["public_sites_modified"])
            self.assertEqual(result["finished_products_published_by_this_dispatch"], 0)
            self.assertEqual(result["remaining_research_diagnostics"]["unresearched_orders"], 200)
            self.assertEqual(result["remaining_research_diagnostics"]["missing_bibliography"], 200)
            self.assertEqual(result["production_outcome"], "audit_only")
            self.assertFalse(result["automated_factory_progress_confirmed"])

    def test_green_worker_exits_without_artifacts_are_reported_as_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            area = root / "production-instructions"
            ops = Path(directory) / "operations/production-instructions"
            area.mkdir(parents=True)
            ops.mkdir(parents=True)
            orders = ["WO-%08d" % i for i in range(1, 201)]
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": orders}), encoding="utf8")
            with mock.patch.object(module, "worker_command", return_value=["true"]):
                with mock.patch.object(module.subprocess, "run",
                                       return_value=SimpleNamespace(returncode=0)):
                    report = module.dispatch(root, ops)
            self.assertEqual(report["production_outcome"], "blocked_no_progress")
            self.assertTrue(report["workers_success_does_not_mean_products_completed"])
            self.assertFalse(report["automated_factory_progress_confirmed"])
            self.assertEqual(report["finished_products_published_by_this_dispatch"], 0)
            self.assertTrue(all(value == "ok" for value
                                in report["worker_results"].values()))
            with mock.patch.object(module, "worker_command", return_value=["true"]):
                with mock.patch.object(module.subprocess, "run",
                                       return_value=SimpleNamespace(returncode=3)):
                    failed = module.dispatch(root, ops)
            self.assertEqual(failed["production_outcome"], "worker_failure")
            self.assertFalse(failed["public_sites_modified"])

    def test_duplicate_internal_orders_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            area = root / "production-instructions"
            area.mkdir()
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": ["WO-00000001"] * 200}))
            with self.assertRaisesRegex(RuntimeError, "INDEX_INTEGRITY_FAILED"):
                module.indexed_orders(root)

    def test_stage_order_has_no_fake_approval_or_store_step(self):
        labels = [stage[0] for stage in module.STAGES]
        self.assertEqual(labels, [
            "outside_literature_scout", "scientific_research",
            "bilingual_design_and_prototype", "private_workbook_draft",
            "technical_preflight_and_rework", "source_specific_revision_brief"])
        self.assertTrue(all("publish" not in label and "approve" not in label
                            for label in labels))


if __name__ == "__main__":
    unittest.main()
