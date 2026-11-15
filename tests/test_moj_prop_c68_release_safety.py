"""Isolated real filesystem acceptance of the exact Moj Prop cPanel updater."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts import update_mojplaywin_moj_prop_catalog as release

ROOT = Path(__file__).resolve().parents[1]


class OneFileHotfixReleaseTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.docroot=self.home/"mojplaywin.com"
        self.route=self.docroot/"moj-prop"
        self.backups=self.home/".mojplaywin-backups"
        self.stage=self.home/".mojplaywin-moj-prop-catalog-123"/"templates"/"moj-prop-v4"
        self.stage.joinpath("catalog").mkdir(parents=True)
        self.route.joinpath("catalog").mkdir(parents=True)
        self.previous=b"<title>Moj Prop | Risk-first prop trading and market intelligence</title>Old."
        (self.route/"index.html").write_bytes(self.previous)
        for name in (".htaccess", "passenger_wsgi.py"):
            (self.docroot/name).write_text("existing")
        self.new=(ROOT/"templates/moj-prop-v4/index.html").read_bytes()
        self.catalog=(ROOT/"templates/moj-prop-v4/catalog/index.html").read_bytes()
        (self.stage/"index.html").write_bytes(self.new)
        (self.stage/"catalog/index.html").write_bytes(self.catalog)
        for name,value in [
            ("HOME",self.home),("DOCROOT",self.docroot),
            ("ROUTE",self.route),("BACKUPS",self.backups),
        ]:
            change=patch.object(release,name,value)
            change.start()
            self.addCleanup(change.stop)
        user=patch.object(release.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="zomorod2"))
        user.start()
        self.addCleanup(user.stop)

    def test_real_staged_customer_form_preflight_passes(self):
        self.assertEqual(release.staged_root("123"),self.stage)

    def test_staging_does_not_admit_missing_horizon_values(self):
        (self.stage/"index.html").write_bytes(
            self.new.replace(b'<option value="week">',b"<option>"))
        with self.assertRaisesRegex(RuntimeError,"Moj Prop index validation failed"):
            release.staged_root("123")

    def test_staging_does_not_admit_missing_consent(self):
        (self.stage/"index.html").write_bytes(
            self.new.replace(
                b"I consent to storing my contact details and request notes",
                b"I did not consent",
            ))
        with self.assertRaisesRegex(RuntimeError,"index validation failed"):
            release.staged_root("123")

    def test_success_backups_and_writes_exact_customer_hotfix(self):
        release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.new)
        self.assertEqual((self.route/"catalog/index.html").read_bytes(),self.catalog)
        self.assertTrue((self.backups/"moj-prop-catalog-123"/"manifest.json").is_file())

    def test_failed_second_file_restores_original_index(self):
        atomic=release.atomic_write
        def fail_second(path,content,mode=0o644):
            if path==self.route/"catalog/index.html":
                raise OSError("simulated full storage")
            return atomic(path,content,mode)
        with patch.object(release,"atomic_write",side_effect=fail_second):
            with self.assertRaisesRegex(OSError,"full storage"):
                release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.previous)
        self.assertFalse((self.route/"catalog/index.html").exists())

    def test_roll_back_only_when_exact_manifest_matches(self):
        release.deploy("123","a"*40)
        release.rollback("123")
        self.assertEqual((self.route/"index.html").read_bytes(),self.previous)
        self.assertFalse((self.route/"catalog/index.html").exists())

    def test_idempotent_live_payload_needs_no_new_backup(self):
        release.deploy("123","a"*40)
        release.deploy("123","a"*40)
        self.assertEqual(len(list(self.backups.iterdir())),1)

    def test_no_stage_symlink_accepted(self):
        dest=self.stage/"index.html"
        dest.unlink()
        dest.symlink_to(self.stage/"catalog/index.html")
        with self.assertRaisesRegex(RuntimeError,"unsafe staged file"):
            release.deploy("123","a"*40)

    def test_no_wrong_cpanel_owner_release(self):
        with patch.object(release.pwd,"getpwuid",
                          return_value=SimpleNamespace(pw_name="root")):
            with self.assertRaisesRegex(RuntimeError,"Unexpected cPanel account"):
                release.deploy("123","a"*40)
        self.assertFalse(self.backups.exists())

    def test_foreign_unverified_existing_catalog_not_overwritten(self):
        (self.route/"catalog/index.html").write_text("different approved rights")
        with self.assertRaisesRegex(RuntimeError,"differs from the approved payload"):
            release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.previous)

    def test_symlinked_backup_root_refuses_deploy_without_touching_live_index(self):
        target=self.home/"unrelated-private-dir"
        target.mkdir()
        self.backups.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,"backup root is a symlink"):
            release.deploy("123","a"*40)
        self.assertEqual((self.route/"index.html").read_bytes(),self.previous)
        self.assertEqual(list(target.iterdir()),[])

    def test_symlinked_backup_root_refuses_rollback_without_touching_target(self):
        target=self.home/"unrelated-private-dir"
        target.mkdir()
        self.backups.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError,"rollback backup path is a symlink"):
            release.rollback("123")
        self.assertEqual((self.route/"index.html").read_bytes(),self.previous)
        self.assertEqual(list(target.iterdir()),[])
