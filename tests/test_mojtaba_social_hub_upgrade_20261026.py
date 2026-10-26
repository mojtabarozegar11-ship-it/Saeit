"""Disposable integration tests for successive personal-site releases.

No test contacts the network or modifies a production path.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import mojtaba_social_hub_install_personal_20261026 as initial
import mojtaba_social_hub_upgrade_personal_20261026 as repeat

class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.app=self.root/"personal"
        self.app.mkdir()
        (self.app/"config").mkdir()
        (self.app/"manage.py").write_text(
            'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\n')
        (self.app/"config"/"settings.py").write_text('ROOT_URLCONF = "config.urls"\n')
        self.urls=self.app/"config"/"urls.py"
        self.urls.write_text("from django.urls import path\nurlpatterns = []\n")
        self.source=ROOT/"social_hub"
        self.backup=self.root/"backups"
        self.private=self.root/"private"
        self.initial_id="release-100001"
        initial.install(self.app,self.source,self.backup,self.private,self.initial_id)
        self.original_code=initial._sources(self.app/"social_hub")
        self.original_route=self.urls.read_bytes()
        self.original_private=(self.private/"social.sqlite").read_bytes()
        self.new_source=self.root/"source"/"social_hub"
        self.new_source.parent.mkdir()
        shutil.copytree(self.source,self.new_source,
                         ignore=shutil.ignore_patterns("__pycache__","*.pyc"))
        cat=self.new_source/"catalog.py"
        cat.write_text(cat.read_text(encoding="utf-8")+"\n# tested backward-compatible code revision\n")
        self.next_id="release-100002"

    def tearDown(self):
        self.temp.cleanup()

    def test_upgrade_only_isolated_package_and_preserve_db(self):
        result=repeat.check(self.app,self.new_source,self.backup)
        self.assertEqual(result["status"],"ready_upgrade")
        data=repeat.upgrade(self.app,self.new_source,self.backup,self.next_id)
        self.assertEqual(data["status"],"upgraded")
        self.assertEqual(self.urls.read_bytes(),self.original_route)
        self.assertEqual((self.private/"social.sqlite").read_bytes(),self.original_private)
        self.assertIn(b"tested backward-compatible", (self.app/"social_hub"/"catalog.py").read_bytes())
        self.assertEqual(repeat.check(self.app,self.new_source,self.backup)["status"],"already_current")
        self.assertTrue((self.backup/self.next_id/"prior_package"/"site_config.py").exists())
        rollback=repeat.rollback(self.app,self.backup,self.next_id)
        self.assertEqual(rollback["status"],"rolled_back")
        self.assertEqual(initial._sources(self.app/"social_hub"),self.original_code)
        self.assertEqual(self.urls.read_bytes(),self.original_route)
        self.assertEqual((self.private/"social.sqlite").read_bytes(),self.original_private)

    def test_in_place_modified_package_fails_closed(self):
        (self.app/"social_hub"/"catalog.py").write_text("untrusted edits",encoding="utf-8")
        with self.assertRaises(initial.InstallationBlocked):
            repeat.upgrade(self.app,self.new_source,self.backup,self.next_id)
        self.assertFalse((self.backup/self.next_id).exists())

    def test_existing_route_changed_fails_closed(self):
        with self.urls.open("a") as fp: fp.write("# unrelated route modification\n")
        with self.assertRaises(initial.InstallationBlocked):
            repeat.check(self.app,self.new_source,self.backup)

    def test_no_upgrade_when_version_identical(self):
        result=repeat.upgrade(self.app,self.source,self.backup,self.next_id)
        self.assertEqual(result["status"],"already_current")
        self.assertFalse((self.backup/self.next_id).exists())

    def test_rollback_refuses_changed_current_version(self):
        repeat.upgrade(self.app,self.new_source,self.backup,self.next_id)
        (self.app/"social_hub"/"catalog.py").write_text("tampered",encoding="utf-8")
        with self.assertRaises(initial.InstallationBlocked):
            repeat.rollback(self.app,self.backup,self.next_id)
        self.assertIn(b"tampered",(self.app/"social_hub"/"catalog.py").read_bytes())

    def test_other_website_file_unaffected(self):
        marker=self.root/"company-site.php"
        marker.write_text("untouched")
        repeat.upgrade(self.app,self.new_source,self.backup,self.next_id)
        self.assertEqual(marker.read_text(),"untouched")

if __name__=="__main__":
    unittest.main()
