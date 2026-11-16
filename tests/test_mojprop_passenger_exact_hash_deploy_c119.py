"""C119: release installer must NEVER trust a WSGI comment/string path.

Offline filesystem-only tests. No DB, deploy, process restart, payment or HTTP.
"""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_mojplaywin_moj_prop_backend as installer


class ExactPassengerPreflightC119Tests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.docroot = Path(self.d.name)
        self.launcher = self.docroot / "passenger_wsgi.py"
        self.source = ("import sys\n"
                       "sys.path.insert(0,'/home/zomorod2/Saeit-staging')\n"
                       "from config.wsgi import application\n")
        self.launcher.write_text(self.source, encoding="utf-8")
        self.launcher.chmod(0o600)

    def verify(self):
        sha = hashlib.sha256(self.launcher.read_bytes()).hexdigest()
        with patch.object(installer, "REVIEWED_PASSENGER_SHA256", sha):
            return installer.verify_reviewed_passenger_entrypoint(self.docroot)

    def test_01_exact_pinned_safe_single_owner_file_is_accepted(self):
        self.assertIsNone(self.verify())

    def test_02_benign_comment_append_changes_hash_and_denies_release(self):
        expected = hashlib.sha256(self.launcher.read_bytes()).hexdigest()
        self.launcher.write_text(self.source + "# reviewed-path later changed\n")
        with patch.object(installer, "REVIEWED_PASSENGER_SHA256", expected):
            with self.assertRaisesRegex(RuntimeError, "SHA differs"):
                installer.verify_reviewed_passenger_entrypoint(self.docroot)

    def test_03_group_or_world_writable_launcher_denied(self):
        for mode in (0o620, 0o602, 0o666):
            with self.subTest(mode=oct(mode)):
                self.launcher.chmod(mode)
                with self.assertRaisesRegex(RuntimeError, "unsafe"):
                    self.verify()
        self.launcher.chmod(0o600)


    def test_05_hardlinked_launcher_denied(self):
        alias = self.docroot / "extra-link"
        os.link(self.launcher, alias)
        try:
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                self.verify()
        finally:
            alias.unlink()

    def test_06_foreign_owner_denied_even_with_identical_bytes(self):
        with patch("scripts.deploy_mojplaywin_moj_prop_backend.os.geteuid",
                   return_value=os.geteuid() + 1):
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                installer.verify_reviewed_passenger_entrypoint(self.docroot)


    def test_07_oversized_launcher_denied_without_parsing_or_execution(self):
        self.launcher.write_bytes(b"#" * 32769)
        with self.assertRaisesRegex(RuntimeError, "unsafe"):
            installer.verify_reviewed_passenger_entrypoint(self.docroot)

    def test_08_missing_launcher_returns_bounded_nonsecret_failure(self):
        self.launcher.unlink()
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            installer.verify_reviewed_passenger_entrypoint(self.docroot)


    def test_09_preflight_occurs_before_any_backup_or_sql_migration(self):
        source = (Path(__file__).resolve().parents[1] /
                  "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        start = source.index("def deploy(")
        check = source.index("verify_reviewed_passenger_entrypoint(DOCROOT)", start)
        restore = source.index("require_independent_db_restore(", start)
        backup = source.index("backup.mkdir(", start)
        ddl = source.index("mark_schema_migration_started(backup)", start)
        self.assertLess(check, restore)
        self.assertLess(restore, backup)
        self.assertLess(backup, ddl)

    def test_10_a_known_staging_path_in_comment_cannot_bypass_exact_hash(self):
        comment = "# /home/zomorod2/Saeit-staging\n"
        self.launcher.write_text(comment + "application=None\n")
        with self.assertRaisesRegex(RuntimeError, "SHA differs"):
            installer.verify_reviewed_passenger_entrypoint(self.docroot)

    def test_04_symlink_launcher_denied_before_content_read(self):
        backup = self.docroot / "inside-real-launcher"
        self.launcher.rename(backup)
        self.launcher.symlink_to(backup)
        with self.assertRaisesRegex(RuntimeError, "symlink refused"):
            self.verify()
