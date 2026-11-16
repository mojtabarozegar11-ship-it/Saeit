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

    def test_04_symlink_launcher_denied_before_content_read(self):
        backup = self.docroot / "inside-real-launcher"
        self.launcher.rename(backup)
        self.launcher.symlink_to(backup)
        with self.assertRaisesRegex(RuntimeError, "symlink refused"):
            self.verify()
