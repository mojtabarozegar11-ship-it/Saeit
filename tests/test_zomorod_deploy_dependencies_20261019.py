"""Regression guard for root Django app deployment dependency restoration."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/zomorod-app-pages-deploy.yml"


class ZomorodRootDependencyTests(unittest.TestCase):
    def test_missing_farnaz_app_is_packaged_for_root_only(self):
        source=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("command_center/templates farnaz core/templates/base.html", source)
        self.assertIn("config core command_center farnaz", source)
        self.assertIn("farnaz/migrations farnaz/templates command_center/templates", source)
        self.assertIn('target="$app/$rel"', source)
        self.assertIn("rollback()", source)
        self.assertNotIn('target="$public_root/farnaz/', source)

    def test_farnaz_django_app_matches_installed_apps(self):
        cfg=(ROOT/"config/settings.py").read_text(encoding="utf-8")
        self.assertIn('"farnaz.apps.FarnazConfig"', cfg)
        for path in ("farnaz/__init__.py","farnaz/apps.py","farnaz/models.py",
                     "farnaz/urls.py","farnaz/migrations/0001_initial.py",
                     "command_center/templates/command_center/dashboard.html"):
            self.assertTrue((ROOT/path).is_file(), path)


if __name__=="__main__":
    unittest.main()
