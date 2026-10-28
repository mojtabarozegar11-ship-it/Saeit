"""Regression checks: owned Arena upgrades must never overwrite unknown live content."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SRC = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("arena_guard", SRC / "scripts/deploy_mpw_arena_static.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GuardedArenaPublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "zomorod2"
        self.root = self.home / "mojplaywin.com"
        self.root.mkdir(parents=True)
        (self.root / ".htaccess").write_text("SHARED_PASSENGER_PROTECTED\n")
        (self.root / "passenger_wsgi.py").write_text("# protected\n")
        existing = self.root / "game-releases/20261020/index.html"
        existing.parent.mkdir(parents=True)
        existing.write_text("Five Original Browser Games")
        self.protected = {
            name: (self.root / name).read_bytes()
            for name in (".htaccess", "passenger_wsgi.py")
        }
        self.patches = [
            mock.patch.object(guard, "HOME", self.home),
            mock.patch.object(guard, "SITE", self.root),
            mock.patch.object(guard, "TARGET", self.root / "arena"),
            mock.patch.object(guard, "PROVEN_STATIC", existing),
            mock.patch.object(guard, "BACKUPS", self.home / ".mojplaywin-arena-failed-releases"),
            mock.patch.object(guard.pwd, "getpwuid", return_value=SimpleNamespace(pw_name="zomorod2")),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def stage(self, run, source):
        directory = self.home / (".mpw-arena-" + run) / "site_releases/mojplaywin/arena"
        directory.mkdir(parents=True)
        (directory / "index.html").write_text(source, encoding="utf-8")
        (directory / "README.md").write_text("free-play games only")
        return directory

    def assert_protected_intact(self):
        for name, data in self.protected.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_additive_install_owned_upgrade_and_exact_rollback(self):
        content = (SRC / "site_releases/mojplaywin/arena/index.html").read_text(encoding="utf-8")
        self.stage("101", content)
        guard.deploy("101", "a" * 40)
        initial = (self.root / "arena/index.html").read_bytes()
        self.assertEqual(guard.read_owner(self.root / "arena")["run_id"], "101")
        self.stage("102", content + "\n<!-- nonfinancial regression revision -->\n")
        guard.deploy("102", "b" * 40)
        self.assertEqual(guard.read_owner(self.root / "arena")["run_id"], "102")
        self.assertEqual((guard.BACKUPS / "prior-102/index.html").read_bytes(), initial)
        self.assert_protected_intact()
        guard.rollback("102", "b" * 40)
        self.assertEqual((self.root / "arena/index.html").read_bytes(), initial)
        self.assertEqual(guard.read_owner(self.root / "arena")["run_id"], "101")
        self.assertTrue((guard.BACKUPS / "failed-live-102/index.html").is_file())
        self.assert_protected_intact()

    def test_foreign_directory_and_tamper_refuse_upgrade(self):
        content = (SRC / "site_releases/mojplaywin/arena/index.html").read_text(encoding="utf-8")
        (self.root / "arena").mkdir()
        (self.root / "arena/other.html").write_text("unowned")
        self.stage("103", content)
        with self.assertRaisesRegex(RuntimeError, "unowned additions"):
            guard.deploy("103", "c" * 40)
        self.assertEqual((self.root / "arena/other.html").read_text(), "unowned")
        self.assert_protected_intact()

    def test_modified_owned_content_refuses_upgrade(self):
        content = (SRC / "site_releases/mojplaywin/arena/index.html").read_text(encoding="utf-8")
        self.stage("104", content)
        guard.deploy("104", "d" * 40)
        (self.root / "arena/index.html").write_text("unexpected external edit")
        self.stage("105", content + "\n<!-- revision -->")
        with self.assertRaisesRegex(RuntimeError, "modified outside release"):
            guard.deploy("105", "e" * 40)
        self.assertEqual((self.root / "arena/index.html").read_text(), "unexpected external edit")
        self.assert_protected_intact()


if __name__ == "__main__":
    unittest.main()
