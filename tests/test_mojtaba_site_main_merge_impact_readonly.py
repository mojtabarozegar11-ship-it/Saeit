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


if __name__ == "__main__":
    unittest.main()
