"""Real filesystem rollback/preflight tests for Moj Prop's existing cPanel deploy."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts import update_mojplaywin_moj_prop_catalog as release


class MojPropC67AtomicReleaseTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.docroot=self.home/"mojplaywin.com"
        self.route=self.docroot/"moj-prop"
        self.backups=self.home/".mojplaywin-backups"
        self.staged=self.home/".mojplaywin-moj-prop-catalog-123"/"templates"/"moj-prop-v4"
        (self.route/"catalog").mkdir(parents=True)
        self.staged.joinpath("catalog").mkdir(parents=True)
        (self.docroot/"passenger_wsgi.py").write_text("valid entrypoint")
        (self.docroot/".htaccess").write_text("existing")
        self.original=("<title>Moj Prop | Risk-first prop trading and market intelligence</title>"
                       "<p>Previous verified content</p>").encode()
        (self.route/"index.html").write_bytes(self.original)
        repo=Path(__file__).resolve().parents[1]
        self.new_index=(repo/"templates/moj-prop-v4/index.html").read_bytes()
        self.new_catalog=(repo/"templates/moj-prop-v4/catalog/index.html").read_bytes()
        self.staged.joinpath("index.html").write_bytes(self.new_index)
        self.staged.joinpath("catalog/index.html").write_bytes(self.new_catalog)
        patches=[
            patch.object(release,"HOME",self.home),
            patch.object(release,"DOCROOT",self.docroot),
            patch.object(release,"ROUTE",self.route),
            patch.object(release,"BACKUPS",self.backups),
            patch.object(release.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="zomorod2")),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_preflight_accepts_exact_existing_form_contract(self):
        self.assertEqual(release.staged_root("123"),self.staged)

    def test_preflight_rejects_unmapped_horizon_codes(self):
        page=self.new_index.replace(b'<option value="week">',b'<option>')
        (self.staged/"index.html").write_bytes(page)
        with self.assertRaisesRegex(RuntimeError,"value=\\\"week"):
            release.staged_root("123")

    def test_preflight_rejects_missing_explicit_consent(self):
        page=self.new_index.replace(
            b"I consent to storing my name, email, and request notes",
            b"No privacy information")
        (self.staged/"index.html").write_bytes(page)
        with self.assertRaisesRegex(RuntimeError,"I consent to storing"):
            release.staged_root("123")

    def test_catalog_write_error_restores_old_index(self):
        original_write=release.atomic_write
        def fault(path,blob,mode=0o644):
            if path==self.route/"catalog/index.html":
                raise OSError("catalog filesystem full")
            return original_write(path,blob,mode)
        with patch.object(release,"atomic_write",side_effect=fault):
            with self.assertRaisesRegex(OSError,"catalog filesystem full"):
                release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.original)
        self.assertFalse((self.route/"catalog/index.html").exists())

    def test_index_write_error_keeps_existing_index(self):
        with patch.object(release,"atomic_write",side_effect=OSError("index cannot write")):
            with self.assertRaisesRegex(OSError,"index cannot write"):
                release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.original)

    def test_success_creates_index_catalog_and_verifiable_backup(self):
        release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.new_index)
        self.assertEqual((self.route/"catalog/index.html").read_bytes(),self.new_catalog)
        self.assertTrue((self.backups/"moj-prop-catalog-123/manifest.json").is_file())

    def test_existing_approved_payload_is_idempotent(self):
        release.deploy("123","a"*40)
        release.deploy("123","a"*40)
        self.assertEqual(len(list(self.backups.iterdir())),1)

    def test_rollback_restores_index_and_removes_only_created_catalog(self):
        release.deploy("123","a"*40)
        release.rollback("123")
        self.assertEqual((self.route/"index.html").read_bytes(),self.original)
        self.assertFalse((self.route/"catalog/index.html").exists())

    def test_unknown_rollback_run_does_not_overwrite_merchant_content(self):
        release.rollback("999")
        self.assertEqual((self.route/"index.html").read_bytes(),self.original)

    def test_wrong_operator_refused_without_backup(self):
        with patch.object(release.pwd,"getpwuid",return_value=SimpleNamespace(pw_name="root")):
            with self.assertRaisesRegex(RuntimeError,"Unexpected cPanel account"):
                release.deploy("123","a"*40)
        self.assertFalse(self.backups.exists())

    def test_bad_staged_symlink_refused_without_backup(self):
        path=self.staged/"catalog/index.html"
        path.unlink()
        path.symlink_to(self.staged/"index.html")
        with self.assertRaisesRegex(RuntimeError,"unsafe staged file"):
            release.deploy("123","a"*40)
        self.assertFalse(self.backups.exists())

    def test_reject_malformed_commit_sha(self):
        with self.assertRaisesRegex(ValueError,"Invalid source commit"):
            release.deploy("123","not-a-github-sha")
        self.assertFalse(self.backups.exists())
