"""Prevent a timestamp- and size-valid stale .pyc from bypassing pinned TRX code.

Actual subprocess behavior is exercised in isolated temporary directories:
no Django settings, network, wallet, payment, checkout or live DB are used.
"""
import inspect
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch

from scripts import mpw_reconcile_scheduler as scheduler


class ReconcilerPythonImportCacheIsolationTests(TestCase):
    def test_real_stale_timestamp_pyc_is_ignored_by_fresh_pycache_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "isolated_reconciliation_module.py"
            source.write_text('VALUE = "OLD"\n', encoding="utf-8")
            previous = source.stat()
            py_compile.compile(str(source), doraise=True)
            source.write_text('VALUE = "NEW"\n', encoding="utf-8")
            self.assertEqual(source.stat().st_size, previous.st_size)
            os.utime(source, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            executable = sys.executable
            snippet = (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import isolated_reconciliation_module; "
                "print(isolated_reconciliation_module.VALUE)"
            )
            env = os.environ.copy()
            env.pop("PYTHONPYCACHEPREFIX", None)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            naive = subprocess.run(
                [executable, "-B", "-c", snippet, str(root)],
                text=True, capture_output=True, timeout=10, env=env, check=True,
            )
            self.assertEqual(naive.stdout.strip(), "OLD")
            fresh = root / "fresh-never-written-pycache"
            self.assertFalse(fresh.exists())
            cold = subprocess.run(
                [executable, "-B", "-X", "pycache_prefix=" + str(fresh),
                 "-c", snippet, str(root)],
                text=True, capture_output=True, timeout=10,
                env={**env, "PYTHONPYCACHEPREFIX": str(fresh)}, check=True,
            )
            self.assertEqual(cold.stdout.strip(), "NEW")
            self.assertFalse(fresh.exists(), "-B must never populate the fresh prefix")

    def test_new_random_cache_prefix_is_always_nonexistent(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            with patch.object(scheduler, "STATE", state):
                a = scheduler.fresh_python_cache_prefix()
                b = scheduler.fresh_python_cache_prefix()
                self.assertEqual(a.parent, state)
                self.assertEqual(b.parent, state)
                self.assertNotEqual(a, b)
                self.assertFalse(a.exists())
                self.assertFalse(b.exists())

    def test_runner_forces_fresh_prefix_before_financial_subprocess(self):
        source = inspect.getsource(scheduler.run)
        self.assertIn('import_cache_prefix = fresh_python_cache_prefix()', source)
        self.assertIn('"pycache_prefix=" + str(import_cache_prefix)', source)
        self.assertIn('"PYTHONPYCACHEPREFIX": str(import_cache_prefix)', source)
        self.assertIn('"PYTHONDONTWRITEBYTECODE": "1"', source)
        self.assertLess(
            source.index('require_reviewed_payment_command()'),
            source.index('result = subprocess.run('),
        )
        self.assertLess(
            source.index('import_cache_prefix = fresh_python_cache_prefix()'),
            source.index('result = subprocess.run('),
        )

    def test_existing_random_prefix_is_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            expected = state / ".cold-import-colliding"
            expected.mkdir()
            with patch.object(scheduler, "STATE", state), patch.object(
                scheduler.secrets, "token_hex", return_value="colliding"
            ):
                with self.assertRaisesRegex(ValueError, "not empty"):
                    scheduler.fresh_python_cache_prefix()
