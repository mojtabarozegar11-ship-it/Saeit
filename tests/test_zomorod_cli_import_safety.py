"""Staged Zomorod site verifiers must never execute while pytest collects tests.

These are manual, explicitly staged filesystem regression scripts. Importing
them must not read a fake -q/old directory, write files or demand CLI args.
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    ("scripts/test_zomorod_onepass_20261113.py", "Pass old/new stage root"),
    ("scripts/test_zomorod_vision_ux_20261113.py",
     "Supply locally staged old/new release directory"),
)


class StagedZomorodImportSafetyTests(unittest.TestCase):
    def test_each_script_is_import_safe_when_pytest_passes_q(self):
        for relative, _ in SCRIPTS:
            with self.subTest(script=relative):
                filename = ROOT / relative
                spec = importlib.util.spec_from_file_location(
                    "zomorod_staged_import_" + filename.stem, filename
                )
                module = importlib.util.module_from_spec(spec)
                with mock.patch.object(sys, "argv", ["pytest", "-q"]):
                    spec.loader.exec_module(module)
                self.assertTrue(callable(getattr(module, "main", None)))

    def test_direct_execution_without_stage_fails_with_explicit_usage(self):
        for relative, reason in SCRIPTS:
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, str(ROOT / relative)],
                    cwd=ROOT, capture_output=True, text=True, timeout=15,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(reason, result.stderr + result.stdout)

    def test_cli_stage_argument_does_not_succeed_without_staged_files(self):
        for relative, _ in SCRIPTS:
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, str(ROOT / relative), "-q"],
                    cwd=ROOT, capture_output=True, text=True, timeout=15,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("old/index.html", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
