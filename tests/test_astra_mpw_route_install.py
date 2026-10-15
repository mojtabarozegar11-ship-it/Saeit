"""Safety checks for exact MojPlayWin-only route patch."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

PATH=Path(__file__).resolve().parents[1]/"scripts/astra_mpw_route_install.py"
spec=importlib.util.spec_from_file_location("astra_mpw_route_install",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RouteInstallerTests(unittest.TestCase):
    def make(self,work):
        base=Path(work)
        app=base/"Saeit-staging"
        (app/"core").mkdir(parents=True)
        (app/"config").mkdir()
        (app/"manage.py").write_text("print('dummy')")
        (app/"config/urls.py").write_text(
            "from core.brand import brand_for_request\n"
            "urlpatterns = [\n    path(\"\", branded_home, name=\"home\"),\n]\n")
        source=base/"view.py"
        source.write_text("def astra_preview_page(request, slug=None): return None\n")
        backups=base/"backups"
        backups.mkdir()
        return app,source,backups

    def test_safe_patch_and_idempotence(self):
        with tempfile.TemporaryDirectory() as d:
            app,source,backups=self.make(d)
            draft=mod.plan(app,source,backups)
            self.assertTrue(mod.apply(draft)["modified_url"])
            self.assertNotIn("factory-previews", (app/"config/urls.py").read_text())
            mod.apply(draft,commit=True)
            self.assertIn("factory-previews", (app/"config/urls.py").read_text())
            self.assertTrue((app/"core/astra_preview_views.py").is_file())
            self.assertEqual(len(list(backups.glob("before-astra-preview-urls-*.py"))),1)
            self.assertFalse(mod.apply(mod.plan(app,source,backups),commit=True)["modified_url"])

    def test_duplicate_preexisting_route_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            app,source,backups=self.make(d)
            file=app/"config/urls.py"
            file.write_text(file.read_text()+"\n"+mod.ROUTES[0])
            with self.assertRaisesRegex(ValueError,"partial Astra URL integration"):
                mod.plan(app,source,backups)

    def test_conflicting_module_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            app,source,backups=self.make(d)
            (app/"core/astra_preview_views.py").write_text("print('other')")
            with self.assertRaisesRegex(ValueError,"conflicts"):
                mod.plan(app,source,backups)

    def test_wrong_application_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            app,source,backups=self.make(d)
            with self.assertRaisesRegex(ValueError,"unknown application"):
                mod.plan(app/"core",source,backups)


if __name__=="__main__":
    unittest.main()
