"""Release safety and deterministic dispatch tests for the 200 P0 orders."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
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
            # Fully valid intake is required before the genuine workers may run.
            (area / "orders").mkdir()
            for ident in orders:
                (area / "orders" / (ident + ".json")).write_text(json.dumps({
                    "id": ident, "status": "issued", "fingerprint": "a" * 64
                }), encoding="utf8")
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

    def test_owner_cleanup_missing_intake_skips_all_mutating_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            area = root / "production-instructions"
            ops = Path(directory) / "operations/production-instructions"
            area.mkdir(parents=True)
            ops.mkdir(parents=True)
            names = ["WO-%08d" % i for i in range(1, 201)]
            (area / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": names}), encoding="utf8")
            with mock.patch.object(module, "worker_command",
                                   side_effect=AssertionError("MUST_NOT_RUN")):
                report = module.dispatch(root, ops)
            self.assertEqual(report["production_outcome"],
                             "blocked_incomplete_stage1_intake")
            self.assertEqual(report["intake_integrity"]["missing"], 200)
            self.assertEqual(report["intake_integrity"]["valid"], 0)
            self.assertFalse(report["automated_factory_progress_confirmed"])
            self.assertEqual(report["worker_results"], {})
            self.assertFalse(report["public_sites_modified"])

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


    @staticmethod
    def _preflight_program():
        workflow = (SOURCE.parents[1] / ".github/workflows/"
                    "factory-agri200-onepass-dispatch-20261023.yml")
        text = workflow.read_text(encoding="utf8")
        start = "ssh_vps 'python3 -B -' <<'PREFLIGHT'\n"
        assert start in text
        program = text.split(start, 1)[1].split("\n          PREFLIGHT", 1)[0]
        return text, textwrap.dedent(program)

    def test_schedule_has_readonly_gate_before_any_vps_write(self):
        text, program = self._preflight_program()
        self.assertLess(text.index("AGRI200_PREFLIGHT=PASS"),
                        text.index("install -d -m 700 '$staging'"))
        self.assertLess(text.index("AGRI200_PREFLIGHT=PASS"),
                        text.index("cat > '$staging/dispatch.py'"))
        self.assertIn("5 * 1024**3 + 128 * 1024**2", program)
        self.assertIn("BLOCKED_INCOMPLETE_INTAKE", program)
        self.assertIn("BLOCKED_DISK_RACE", program)
        self.assertIn("StrictHostKeyChecking=yes", text)
        self.assertIn("AGRI200_NO_VERIFIED_PRODUCTION_PROGRESS", text)
        compile(program, "<read-only-preflight>", "exec")

    def test_real_preflight_blocks_missing_intake_before_mutations(self):
        _, program = self._preflight_program()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "private/autonomous-product-cycle/production-instructions"
            root.mkdir(parents=True)
            (root / "orders").mkdir()
            ids = ["WO-%08d" % i for i in range(1, 201)]
            (root / "owner-agri200-p0-index.json").write_text(json.dumps({
                "topic_count": 200, "edition_goal_count": 400,
                "order_ids_ranked": ids}), encoding="utf8")
            replacement = (
                'base = Path("/home/githubops/factory-runtime")',
                "base = Path(" + repr(str(base)) + ")")
            simulation = program.replace(*replacement)
            simulation = simulation.replace("free = shutil.disk_usage(base).free",
                                            "free = 6 * 1024**3")
            simulation = simulation.replace("if shutil.disk_usage(base).free < minimum:",
                                            "if False:")
            blocked = subprocess.run(["python3", "-B", "-"], input=simulation,
                                     text=True, capture_output=True, check=False)
            self.assertEqual(blocked.returncode, 4, blocked.stderr)
            self.assertIn("BLOCKED_INCOMPLETE_INTAKE", blocked.stdout)
            self.assertEqual(list((root / "orders").iterdir()), [])
            for ident in ids:
                (root / "orders" / (ident + ".json")).write_text(json.dumps({
                    "id": ident, "status": "issued", "fingerprint": "b" * 64}),
                    encoding="utf8")
            allowed = subprocess.run(["python3", "-B", "-"], input=simulation,
                                     text=True, capture_output=True, check=False)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertIn("AGRI200_PREFLIGHT=PASS", allowed.stdout)
            no_space = simulation.replace("free = 6 * 1024**3", "free = 1")
            rejected = subprocess.run(["python3", "-B", "-"], input=no_space,
                                      text=True, capture_output=True, check=False)
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.assertIn("BLOCKED_DISK_RESERVE", rejected.stdout)


if __name__ == "__main__":
    unittest.main()
