"""Regression checks for the live Zomorod deploy rollback-backup guard."""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/zomorod-app-pages-deploy.yml"


def exclusive_backup_shell():
    source = WORKFLOW.read_text(encoding="utf-8")
    assert 'rm -rf -- "$backup"' not in source
    assert source.count("ZM_DEPLOY_BACKUP_EXCLUSIVE_BEGIN") == 1
    assert source.count("ZM_DEPLOY_BACKUP_EXCLUSIVE_END") == 1
    lines = source.splitlines()
    start = next(i for i, x in enumerate(lines) if "ZM_DEPLOY_BACKUP_EXCLUSIVE_BEGIN" in x)
    end = next(i for i, x in enumerate(lines) if "ZM_DEPLOY_BACKUP_EXCLUSIVE_END" in x)
    assert start < end
    assert all(x.startswith("          ") for x in lines[start + 1:end])
    return "\n".join(x[10:] for x in lines[start + 1:end])


class ZomorodBackupExclusiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.backups = self.home / ".backups"
        self.backups.mkdir(mode=0o700)

    def invoke(self, sha="a" * 40):
        block = exclusive_backup_shell()
        script = (
            'backup_root="$HOME/.backups/zomorodmelal-app"\n'
            f'backup="$backup_root/{sha}"\n'
            + block + "\n"
        )
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        return subprocess.run(
            ["bash", "-euo", "pipefail", "-c", script],
            env=env, text=True, capture_output=True, check=False,
        )

    def test_first_backup_is_created_private_and_exclusive(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        directory = self.backups / "zomorodmelal-app" / ("a" * 40)
        self.assertTrue(directory.is_dir())
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)

    def test_rerun_preserves_original_rollback_bytes(self):
        self.assertEqual(self.invoke().returncode, 0)
        backup = self.backups / "zomorodmelal-app" / ("a" * 40)
        original = backup / "deployed.flag"
        original.write_bytes(b"immutable deployment proof\n")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EXISTING_DEPLOY_BACKUP_PRESERVED", result.stderr)
        self.assertEqual(original.read_bytes(), b"immutable deployment proof\n")

    def test_existing_incomplete_backup_also_fails_closed(self):
        root = self.backups / "zomorodmelal-app" / ("a" * 40)
        root.mkdir(parents=True)
        (root / "existing.txt").write_text("rollback data", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((root / "existing.txt").read_text(), "rollback data")

    def test_symlinked_backup_root_is_never_followed(self):
        actual = self.home / "other"
        actual.mkdir()
        (self.backups / "zomorodmelal-app").symlink_to(actual, target_is_directory=True)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])

    def test_symlinked_backup_leaf_is_not_overwritten(self):
        root = self.backups / "zomorodmelal-app"
        root.mkdir()
        target = self.home / "valuable"
        target.write_text("keep me", encoding="utf-8")
        (root / ("a" * 40)).symlink_to(target)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), "keep me")

    def test_symlinked_parent_backup_area_is_rejected(self):
        self.backups.rmdir()
        actual = self.home / "other"
        actual.mkdir()
        self.backups.symlink_to(actual, target_is_directory=True)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
