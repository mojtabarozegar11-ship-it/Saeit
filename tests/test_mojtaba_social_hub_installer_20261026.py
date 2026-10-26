"""Safe installer tests against disposable personal-Django fixtures, never production."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "social_site_installer", ROOT/"scripts/mojtaba_social_hub_install_personal_20261026.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class PersonalInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.app=self.root/"mojtaba_personal"
        self.app.mkdir()
        (self.app/"site").mkdir()
        (self.app/"manage.py").write_text(
            "import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','site.settings')\n")
        (self.app/"site"/"settings.py").write_text("ROOT_URLCONF = 'site.urls'\n")
        self.urls=self.app/"site"/"urls.py"
        self.original="from django.urls import path\nurlpatterns = []\n"
        self.urls.write_text(self.original)
        self.source=ROOT/"social_hub"
        self.backup=self.root/"private_backups"
        self.private=self.root/"private_database"

    def tearDown(self):
        self.tmp.cleanup()

    def test_check_does_not_mutate(self):
        result=installer.plan(self.app,self.source)
        self.assertGreaterEqual(len(result["package_files"]),7)
        self.assertEqual(self.urls.read_text(),self.original)
        self.assertFalse((self.app/"social_hub").exists())

    def test_install_and_rollback_preserves_original(self):
        unrelated=self.root/"another_site.txt"
        unrelated.write_text("untouched")
        run="test-run-123456"
        result=installer.install(self.app,self.source,self.backup,self.private,run)
        self.assertEqual(result["status"],"installed")
        self.assertIn(installer.MARK_BEGIN,self.urls.read_text())
        self.assertTrue((self.app/"social_hub"/"urls.py").is_file())
        self.assertTrue((self.private/"social.sqlite").is_file())
        rollback=installer.rollback(self.app,self.backup,run)
        self.assertEqual(rollback["status"],"rolled_back")
        self.assertEqual(self.urls.read_text(),self.original)
        self.assertFalse((self.app/"social_hub").exists())
        self.assertTrue((self.private/"social.sqlite").is_file())
        self.assertEqual(unrelated.read_text(),"untouched")

    def test_existing_route_or_app_fails_closed(self):
        self.urls.write_text(self.original+"\n# social-command/ route already exists\n")
        with self.assertRaises(installer.InstallationBlocked):
            installer.plan(self.app,self.source)
        self.assertFalse((self.app/"social_hub").exists())

    def test_changed_urlconf_not_rolled_back_automatically(self):
        run="test-run-234567"
        installer.install(self.app,self.source,self.backup,self.private,run)
        with self.urls.open("a") as fp:
            fp.write("\n# changed by site owner\n")
        with self.assertRaises(installer.InstallationBlocked):
            installer.rollback(self.app,self.backup,run)
        self.assertTrue((self.app/"social_hub").exists())

    def test_bad_source_preflight_no_files_written(self):
        with tempfile.TemporaryDirectory() as bad:
            with self.assertRaises(installer.InstallationBlocked):
                installer.install(self.app,Path(bad),self.backup,self.private,"test-run-345678")
            self.assertEqual(self.urls.read_text(),self.original)
            self.assertFalse(self.private.exists())

if __name__=="__main__":
    unittest.main()
