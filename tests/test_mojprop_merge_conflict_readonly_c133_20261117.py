"""Synthetic Git 3-way conflict triage tests. Never touches remote or production."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.mojprop_merge_conflict_readonly_c133 import (
    REFS, PAIRS, _git, _sha, _risk, _valid_path, inspect, main
)


def git(folder: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(folder), *args],
                            capture_output=True, text=True, timeout=12)
    if result.returncode:
        raise AssertionError((args, result.stderr[-400:]))
    return result.stdout.strip()


def fixture(root: Path):
    git(root, "init", "-q")
    git(root, "config", "user.email", "c133@synthetic.invalid")
    git(root, "config", "user.name", "C133 synthetic only")
    (root / "customer-path.txt").write_text("unchanged\n", "utf-8")
    (root / "risk.txt").write_text("base\n", "utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "synthetic base")
    initial = git(root, "rev-parse", "HEAD")
    git(root, "branch", "canonical", initial)
    git(root, "switch", "-q", "canonical")
    (root / "risk.txt").write_text("canonical\n", "utf-8")
    git(root, "commit", "-qam", "canonical test")
    canon = git(root, "rev-parse", "HEAD")
    git(root, "branch", "static", initial)
    git(root, "switch", "-q", "static")
    (root / "risk.txt").write_text("static\n", "utf-8")
    git(root, "commit", "-qam", "static test")
    static = git(root, "rev-parse", "HEAD")
    for name, oid in zip(REFS, (initial, canon, static)):
        git(root, "update-ref", REFS[name], oid)
    git(root, "switch", "-q", "canonical")
    return initial, canon, static


class ConflictInventoryC133Tests(unittest.TestCase):
    def test_pinned_compared_refs_fixed_to_three_branches(self):
        self.assertEqual(set(REFS), {"main", "prop_canonical", "public_static"})
        self.assertEqual(len(PAIRS), 3)

    def test_synthetic_conflicting_feature_branches_are_identified(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            initial, canon, static = fixture(root)
            result = inspect(root, "prop_canonical", "public_static")
            self.assertEqual(result.result, "blocked_by_conflicts")
            self.assertEqual(result.conflicting_paths, ("risk.txt",))
            self.assertEqual(result.count, 1)
            self.assertEqual(len(result.digest), 64)
            self.assertEqual((result.base_sha, result.head_sha), (canon, static))
            self.assertEqual(_sha(root, REFS["main"]), initial)

    def test_main_vs_two_non_conflicting_changes_is_clean(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            for name in ("prop_canonical", "public_static"):
                result = inspect(root, "main", name)
                self.assertEqual(result.result, "clean")
                self.assertEqual(result.count, 0)
                self.assertEqual(result.digest, "")

    def test_simulation_does_not_modify_worktree_or_index(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            before = git(root, "status", "--porcelain")
            index = git(root, "write-tree")
            inspect(root, "prop_canonical", "public_static")
            self.assertEqual(git(root, "status", "--porcelain"), before)
            self.assertEqual(git(root, "write-tree"), index)
            self.assertEqual(git(root, "branch", "--show-current"), "canonical")

    def test_main_job_safely_distinguishes_successful_inventory_from_safe_release(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            original = Path.cwd()
            try:
                os.chdir(root)
                output = StringIO()
                with redirect_stdout(output):
                    code = main(["c133"])
            finally:
                os.chdir(original)
            self.assertEqual(code, 0)
            value = output.getvalue()
            self.assertIn("MOJPROP_C133_CONFLICT_AUDIT=COMPLETE_READONLY", value)
            self.assertIn("PROP_CANONICAL_VS_PUBLIC_STATIC_CONFLICT_COUNT=1", value)
            self.assertIn("MOJPROP_C133_LIVE_RELEASE_AUTHORIZED=false", value)
            self.assertIn("MOJPROP_C133_PAYMENT_OR_CUSTOMER_POST=false", value)
            self.assertIn("RISK_OTHER=1", value)

    def test_missing_ref_does_not_become_zero_conflicts(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            git(root, "update-ref", "-d", REFS["public_static"])
            with self.assertRaisesRegex(RuntimeError, "branch unavailable"):
                inspect(root, "main", "public_static")

    def test_untrusted_ref_names_are_rejected(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            for a, b in (("main", "main"), ("main", "HEAD"), ("unknown", "main")):
                with self.subTest(pair=(a,b)):
                    with self.assertRaises(ValueError):
                        inspect(root, a, b)

    def test_paths_cannot_emit_terminal_controls_or_traversal(self):
        for bad in ("", "/etc/passwd", "../secret", "./secret", "path/../escape",
                    "path/./relative", "buyer\nreceipt", "control\r", "\x00",
                    "x" * 501):
            with self.subTest(value=repr(bad)):
                self.assertFalse(_valid_path(bad))
        self.assertTrue(_valid_path("core/moj_prop_views.py"))

    def test_risk_categories_flag_actual_business_boundaries(self):
        self.assertEqual(_risk("prop_firm/migrations/0008_prospect_contact_intake.py"),
                         "crm_model_consent")
        self.assertEqual(_risk("core/moj_prop_views.py"), "crm_model_consent")
        self.assertEqual(_risk("config/urls.py"), "django_runtime")
        self.assertEqual(_risk(".github/workflows/release.yml"), "ci_deploy_controls")
        self.assertEqual(_risk("templates/moj-prop-v4/index.html"), "public_buyer_ui")
        self.assertEqual(_risk("core/checkout.py"), "payment_boundary")

    def test_no_production_network_email_or_removal_code(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/mojprop_merge_conflict_readonly_c133.py").read_text("utf-8")
        for forbidden in ("requests.", "urllib.request", "smtplib", "os.environ",
                          "git push", "git merge ", "remove(", "delete(",
                          "subprocess.Popen", "cPanel", "TRX_AMOUNT"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"merge-tree"', source)
        self.assertNotIn('"merge",', source)


if __name__ == "__main__":
    unittest.main()
