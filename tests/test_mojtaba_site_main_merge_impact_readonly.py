"""Contract checks for full-checkout PR main-merge impact. No host/network access."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / "scripts" / "mojtaba_site_main_merge_impact_readonly.py"
spec = importlib.util.spec_from_file_location("merge_impact_readonly", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MergeImpactTests(unittest.TestCase):
    def inspect_source(self, source, changed=("core/mojtaba_site_fleet.py",)):
        return module.inspect_text("sample.yml", source, list(changed))

    def test_no_paths_filter_catches_main_push(self):
        r = self.inspect_source("on:\n  push:\n    branches: [main]\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n")
        self.assertEqual(r["classification"], "possible_main_push")

    def test_filter_matches_exact_changed_file(self):
        s = "on:\n  push:\n    branches: [main]\n    paths:\n      - core/mojtaba_site_fleet.py\n"
        self.assertEqual(self.inspect_source(s)["classification"], "possible_main_push")

    def test_unrelated_path_does_not_trigger(self):
        s = "on:\n  push:\n    branches: [main]\n    paths:\n      - core/commerce_views.py\n"
        self.assertEqual(self.inspect_source(s)["classification"], "not_matched")

    def test_other_branch_does_not_trigger_main(self):
        s = "on:\n  push:\n    branches: [develop]\n"
        self.assertEqual(self.inspect_source(s)["classification"], "not_matched")

    def test_broad_glob_conservatively_detected(self):
        s = "on:\n  push:\n    paths: [core/**]\n"
        self.assertEqual(self.inspect_source(s)["classification"], "possible_main_push")

    def test_workflow_run_needs_separate_review(self):
        s = "on:\n  workflow_run:\n    workflows: [CI]\n    types: [completed]\n"
        self.assertEqual(self.inspect_source(s)["classification"], "possible_workflow_run")

    def test_manual_only_not_marked_as_main_push(self):
        s = "on:\n  workflow_dispatch:\n"
        self.assertEqual(self.inspect_source(s)["classification"], "not_matched")

    def test_ambiguous_on_syntax_never_treated_as_safe(self):
        s = "'on':\n  push:\n"
        self.assertEqual(self.inspect_source(s)["classification"], "unknown_on_syntax")

    def test_empty_and_unsafe_input_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(ValueError):
                module.inspect(root, [])
            with self.assertRaises(ValueError):
                module.inspect(root, ["../private/data"])

    def test_unknown_workflow_remains_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / ".github" / "workflows"
            folder.mkdir(parents=True)
            (folder / "opaque.yml").write_text("'on':\n  push:\n")
            r = module.inspect(Path(td), ["core/mojtaba_site_fleet.py"])
            self.assertEqual(r["verdict"], "NO_GO")
            self.assertEqual(r["unknown_count"], 1)
            self.assertFalse(r["merge_authorized"])
            self.assertFalse(r["host_cleanup_authorized"])

    def test_existing_real_repo_never_claims_merge_authorized(self):
        root = Path(__file__).resolve().parents[1]
        result = module.inspect(root, ["core/mojtaba_site_fleet.py"])
        self.assertGreaterEqual(result["workflow_files_scanned"], 1000)
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["live_deployment_authorized"])


    def test_indirect_workflow_run_requires_actual_upstream_causal_trigger(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / ".github" / "workflows"
            folder.mkdir(parents=True)
            (folder / "upstream.yml").write_text(
                "name: Audit Main\non:\n  push:\n    branches: [main]\n")
            (folder / "dependent.yml").write_text(
                "name: Follow Audit\non:\n  workflow_run:\n"
                "    workflows: [Audit Main]\n    types: [completed]\n")
            (folder / "unrelated.yml").write_text(
                "name: Unrelated\non:\n  workflow_run:\n"
                "    workflows: [Unrelated Baseline]\n    types: [completed]\n")
            x = module.inspect(Path(td), ["core/mojtaba_site_fleet.py"])
            ids = {r["workflow"] for r in x["blockers"]}
            self.assertIn("upstream.yml", ids)
            self.assertIn("dependent.yml", ids)
            self.assertNotIn("unrelated.yml", ids)

    def test_workflow_run_specific_other_branch_is_not_merge_causal(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / ".github" / "workflows"
            folder.mkdir(parents=True)
            (folder / "upstream.yml").write_text("name: Audit Main\non:\n  push:\n")
            (folder / "dependent.yml").write_text(
                "on:\n  workflow_run:\n    workflows: [Audit Main]\n"
                "    branches: [feature/not-main]\n")
            r = module.inspect(Path(td), ["core/mojtaba_site_fleet.py"])
            self.assertNotIn("dependent.yml", [x["workflow"] for x in r["blockers"]])

    def test_hardcoded_safe_filename_cannot_bypass_on_changed_blob(self):
        self.assertNotEqual(
            module.git_blob_sha(b"name: CI\non:\n  push:\n"),
            module.REVIEWED_BLOBS["ci.yml"],
        )
        self.assertFalse(module.verified_static_no_host_guard(
            "ci.yml", "name: CI\njobs:\n  test:\n    steps:\n"
            "      - run: ssh root@production\n"
        ))

    def test_manual_release_job_requires_dispatch_guard_on_single_job(self):
        valid = ("jobs:\n  publish:\n"
                 "    if: github.event_name == 'workflow_dispatch'\n"
                 "    runs-on: ubuntu-latest\n")
        invalid = "jobs:\n  publish:\n    runs-on: ubuntu-latest\n"
        self.assertTrue(module.verified_static_no_host_guard(
            "zomorod-app-pages-deploy.yml", valid))
        self.assertFalse(module.verified_static_no_host_guard(
            "zomorod-app-pages-deploy.yml", invalid))


if __name__ == "__main__":
    unittest.main()
