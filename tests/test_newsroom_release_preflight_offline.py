"""Read-only manifest checks without Django or production connectivity."""

import tempfile
import unittest
from pathlib import Path

from deploy.newsroom_release_preflight import git_blob_sha, inspect_release


def manifest(files):
    return {"version": 1, "mode": "READ_ONLY_PREFLIGHT", "commit": "abc", "files": files}


def file_entry(path, payload, change="modified"):
    return {"path": path, "git_blob_sha": git_blob_sha(payload), "change": change}


class ReleasePreflightTests(unittest.TestCase):
    def test_read_only_current_conflict_and_new(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            current = root / "core" / "current.py"
            conflict = root / "core" / "conflict.py"
            current.write_bytes(b"correct")
            conflict.write_bytes(b"local-user-changes")
            before = conflict.read_bytes()
            result = inspect_release(root, manifest([
                file_entry("core/current.py", b"correct"),
                file_entry("core/conflict.py", b"upstream"),
                file_entry("core/new.py", b"new", "added"),
            ]))
            self.assertEqual(result["counts"], {
                "already_current": 1,
                "different_manual_merge_required": 1,
                "new_file_missing": 1,
            })
            self.assertTrue(result["requires_manual_reconciliation"])
            self.assertFalse(result["safe_to_apply_automatically"])
            self.assertEqual(conflict.read_bytes(), before)
            self.assertFalse((root / "core" / "new.py").exists())

    def test_missing_preexisting_file_is_not_approved(self):
        with tempfile.TemporaryDirectory() as d:
            result = inspect_release(Path(d), manifest([file_entry("core/existing.py", b"x")]))
            self.assertEqual(result["counts"], {"modified_file_missing": 1})
            self.assertTrue(result["requires_manual_reconciliation"])

    def test_symlink_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            (root / "core" / "link.py").symlink_to(root / "outside.py")
            result = inspect_release(root, manifest([file_entry("core/link.py", b"x")]))
            self.assertEqual(result["counts"], {"unsafe_symlink": 1})
            for unsafe in ("../core/a.py", "/etc/passwd", "core/../outside", "tests/a.py"):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    inspect_release(root, manifest([file_entry(unsafe, b"x")]))

    def test_invalid_git_sha_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                inspect_release(Path(d), manifest([{"path": "core/x.py", "change": "added", "git_blob_sha": "bad"}]))


if __name__ == "__main__":
    unittest.main()
