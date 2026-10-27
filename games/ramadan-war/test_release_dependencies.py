"""Executable regression tests for Ramadan War's scoped release dependency closure."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ramadan_release_dependencies", HERE / "check_release_dependencies.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReleaseDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "game.js").write_text(
            "import { safe } from './policy.mjs';\n", encoding="utf-8"
        )
        (self.root / "policy.mjs").write_text(
            "export const safe = true;\n", encoding="utf-8"
        )
        self.manifest = "ASSETS=['game.js','policy.mjs']\n"
        self.workflow = "\n".join(
            f'          timeout 50s scp -q -F "$d/config" games/ramadan-war/{name} "host:$stage/incoming/{dest}"'
            for name, dest in [
                ("game.js", "game.js"),
                ("policy.mjs", "policy.mjs"),
                ("deploy.py", "deploy.py"),
                ("route.htaccess", ".htaccess"),
            ]
        )

    def check(self, manifest=None, workflow=None):
        return checker.audit(
            self.root,
            self.manifest if manifest is None else manifest,
            self.workflow if workflow is None else workflow,
        )

    def test_complete_module_closure_passes(self):
        self.assertEqual([], self.check())

    def test_import_missing_from_manifest_fails(self):
        self.assertTrue(any(
            "unbundled JS import" in issue
            for issue in self.check(manifest="ASSETS=['game.js']\n")
        ))

    def test_manifest_asset_missing_from_staging_fails(self):
        workflow = self.workflow.replace(
            'games/ramadan-war/policy.mjs "host:$stage/incoming/policy.mjs"',
            'games/ramadan-war/policy.mjs "host:$stage/incoming/missing.mjs"',
        )
        self.assertTrue(any(
            "asset not staged" in issue for issue in self.check(workflow=workflow)
        ))

    def test_import_escaping_route_fails(self):
        (self.root / "game.js").write_text(
            "import '../private.js';\n", encoding="utf-8"
        )
        self.assertTrue(any(
            "import escapes release route" in issue for issue in self.check()
        ))

    def test_missing_local_file_fails(self):
        (self.root / "policy.mjs").unlink()
        self.assertTrue(any(
            "missing release asset" in issue for issue in self.check()
        ))

    def test_duplicate_manifest_fails(self):
        self.assertTrue(any(
            "duplicate asset" in issue
            for issue in self.check(manifest="ASSETS=['game.js','policy.mjs','policy.mjs']\n")
        ))


if __name__ == "__main__":
    unittest.main()
