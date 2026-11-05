"""Focused regression tests for the durable F-01 singleton root guard."""
import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "factory_global_singleton", ROOT / "scripts/factory_global_singleton_v1.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GlobalSingletonRootTests(unittest.TestCase):
    @staticmethod
    def _info(path, bad=None, mode=None):
        if bad is not None and path == bad:
            return SimpleNamespace(
                st_mode=mode if mode is not None else stat.S_IFDIR | 0o755)
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755)

    def test_protected_ancestry_is_accepted(self):
        root = Path("/srv/saeit/private")
        with patch.object(Path, "lstat", autospec=True,
                          side_effect=lambda path: self._info(path)), \
             patch.object(Path, "resolve", autospec=True,
                          side_effect=lambda path, strict=False: path):
            self.assertEqual(MODULE._safe_root(root), root)

    def test_group_or_other_writable_ancestor_is_rejected(self):
        root = Path("/srv/saeit/private")
        bad = Path("/srv/saeit")
        with patch.object(Path, "lstat", autospec=True,
                          side_effect=lambda path: self._info(
                              path, bad, stat.S_IFDIR | 0o775)):
            with self.assertRaisesRegex(RuntimeError, "ANCESTRY_WRITABLE"):
                MODULE._safe_root(root)

    def test_symlink_ancestor_is_rejected(self):
        root = Path("/srv/saeit/private")
        bad = Path("/srv/saeit")
        with patch.object(Path, "lstat", autospec=True,
                          side_effect=lambda path: self._info(
                              path, bad, stat.S_IFLNK | 0o777)):
            with self.assertRaisesRegex(RuntimeError, "MISSING_OR_UNSAFE"):
                MODULE._safe_root(root)


if __name__ == "__main__":
    unittest.main()
