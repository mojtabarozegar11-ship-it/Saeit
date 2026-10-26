"""No-network route fix regression: no modification outside personal URLconf."""
import sys
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import mojtaba_social_hub_install_personal_20261026 as initial
import mojtaba_social_hub_upgrade_personal_20261026 as release
import mojtaba_social_hub_public_route_fix_20261026 as fix

class PersonalPublicRouteFixTests(unittest.TestCase):
    def setUp(self):
        self.previous_test_flag=os.environ.get("MPW_SOCIAL_INSTALL_TEST")
        os.environ["MPW_SOCIAL_INSTALL_TEST"]="1"
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.app=self.root/"personal"
        (self.app/"config").mkdir(parents=True)
        (self.app/"manage.py").write_text(
            'import os\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\n')
        (self.app/"config"/"settings.py").write_text('ROOT_URLCONF = "config.urls"\n')
        self.urls=self.app/"config"/"urls.py"
        self.urls.write_text("from django.urls import path\nurlpatterns = []\n")
        self.backup=self.root/"restricted_private_backup"
        self.ledger=self.root/"restricted_private_account_data"
        self.shared=self.root/"OTHER_SITE_NEVER_TOUCH"
        self.shared.write_text("untouched",encoding="utf-8")
        self.origin="fixture_initial_123"
        self.fix_id="fixture_public_456"
        initial.install(self.app,ROOT/"social_hub",self.backup,self.ledger,self.origin)
        self.old=self.urls.read_bytes()
        self.old_db=(self.ledger/"social.sqlite").read_bytes()
        self.old_package=initial._sources(self.app/"social_hub")

    def tearDown(self):
        if self.previous_test_flag is None:
            os.environ.pop("MPW_SOCIAL_INSTALL_TEST",None)
        else:
            os.environ["MPW_SOCIAL_INSTALL_TEST"]=self.previous_test_flag
        self.tmp.cleanup()

    def test_exact_prefix_installs_once_and_is_future_upgrade_compatible(self):
        report=fix.check(self.app,self.backup)
        self.assertEqual(report["url_sha"],initial.sha(self.old))
        result=fix.install(self.app,self.backup,self.fix_id)
        self.assertEqual(result["status"],"personal_route_installed")
        self.assertEqual(result["public_prefix"],"/mojtaba.roozegar/social-command/")
        now=self.urls.read_text(encoding="utf-8")
        self.assertTrue(now.startswith(self.old.decode("utf-8")))
        self.assertIn("urlpatterns.insert(0",now)
        self.assertEqual(now.count(fix.MARKER_BEGIN),1)
        self.assertEqual(now.count(fix.PUBLIC_ROUTE),1)
        self.assertEqual(initial._sources(self.app/"social_hub"),self.old_package)
        self.assertEqual((self.ledger/"social.sqlite").read_bytes(),self.old_db)
        self.assertEqual(self.shared.read_text(),"untouched")
        self.assertEqual(release._snapshot_match(self.app,self.backup)["url_sha"],
                         initial.sha(self.urls.read_bytes()))
        with self.assertRaises(initial.InstallationBlocked):
            fix.install(self.app,self.backup,"fixture_public_789")

    def test_runtime_removes_only_old_social_path_and_preserves_unrelated_routes(self):
        class Pattern:
            def __init__(self, route): self.route=route
            def __str__(self): return self.route
        class Entry:
            def __init__(self,route): self.pattern=Pattern(route)
        original=[Entry("mojtaba.roozegar/"),Entry("company/"),Entry("social-command/")]
        def path(route, included): return Entry(route)
        namespace={"urlpatterns":original,"_mpw_social_path":path,
                   "_mpw_social_include":lambda value:value}
        exec(fix.PUBLIC_ROUTE,namespace)
        observed=[str(x.pattern) for x in namespace["urlpatterns"]]
        self.assertEqual(observed.count("mojtaba.roozegar/social-command/"),1)
        self.assertNotIn("social-command/",observed)
        self.assertIn("mojtaba.roozegar/",observed)
        self.assertIn("company/",observed)
        self.assertEqual(observed[0],"mojtaba.roozegar/social-command/")

    def test_rollback_restores_exactly_original_routes_not_private_db(self):
        fix.install(self.app,self.backup,self.fix_id)
        result=fix.rollback(self.app,self.backup,self.fix_id)
        self.assertEqual(result["status"],"personal_route_restored")
        self.assertEqual(self.urls.read_bytes(),self.old)
        self.assertEqual((self.ledger/"social.sqlite").read_bytes(),self.old_db)
        self.assertEqual(self.shared.read_text(),"untouched")
        self.assertEqual(release._snapshot_match(self.app,self.backup)["url_sha"],
                         initial.sha(self.old))

    def test_prior_local_modification_blocks_patch(self):
        self.urls.write_bytes(self.old+b"\n# concurrent owner edit\n")
        with self.assertRaises(initial.InstallationBlocked):
            fix.install(self.app,self.backup,self.fix_id)
        self.assertFalse((self.backup/self.fix_id).exists())

    def test_stale_or_tampered_restore_refused(self):
        fix.install(self.app,self.backup,self.fix_id)
        with self.urls.open("ab") as f:
            f.write(b"\n# another site operator's change\n")
        with self.assertRaises(initial.InstallationBlocked):
            fix.rollback(self.app,self.backup,self.fix_id)

    def test_missing_previous_checksum_backup_blocks_patch(self):
        # The manifest must match the actual current package, not a guessed site.
        (self.app/"social_hub"/"catalog.py").write_text("tampered")
        with self.assertRaises(initial.InstallationBlocked):
            fix.check(self.app,self.backup)

if __name__=="__main__":
    unittest.main()
