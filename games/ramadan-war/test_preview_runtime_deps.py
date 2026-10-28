#!/usr/bin/env python3
"""Prevent a green CI preview from shipping with unresolved local ES module imports."""
import re
import unittest
from pathlib import Path, PurePosixPath

from deploy import ASSETS

ROOT = Path(__file__).resolve().parent
IMPORTS = re.compile(
    r"""(?:^|\n)\s*(?:import\s+(?:[^;\n]*?\s+from\s+)?|export\s+[^;\n]*?\s+from\s+)['"]([^'"]+)['"]""",
    re.MULTILINE,
)
REQUIRED = {
    "upgrade-policy.mjs", "moj1-commerce-policy.mjs", "input-guard.mjs",
    "missile-targets.mjs", "enemy-action-policy.mjs", "save-validation.mjs",
}


class RuntimeDependencyTests(unittest.TestCase):
    def test_all_local_static_module_imports_are_packaged(self):
        declared = set(ASSETS)
        self.assertEqual(len(ASSETS), len(declared), "duplicate deployment asset")
        self.assertTrue(REQUIRED <= declared, "gameplay policy modules absent from preview")
        for name in declared:
            if not name.endswith((".js", ".mjs")):
                continue
            source = (ROOT / name).read_text("utf-8")
            for dependency in IMPORTS.findall(source):
                self.assertTrue(dependency.startswith(("./", "../")), (name, dependency))
                resolved = PurePosixPath(name).parent / dependency
                parts = []
                for part in resolved.parts:
                    if part in ("", "."):
                        continue
                    if part == "..":
                        self.assertTrue(parts, "import escapes game directory")
                        parts.pop()
                    else:
                        parts.append(part)
                normalized = "/".join(parts)
                self.assertIn(normalized, declared, (name, dependency, normalized))
                self.assertTrue((ROOT / normalized).is_file(), normalized)

    def test_live_transfer_matches_the_complete_release_manifest(self):
        """CI release must stage every asset that deploy.prepare() expects."""
        workflow = (ROOT.parents[1] / ".github/workflows/zomorod-ramadan-war-web-card.yml").read_text("utf-8")
        transfers = re.findall(
            r'^\s*timeout\s+\d+s\s+scp\s+-q\s+-F\s+"\$d/config"\s+games/ramadan-war/(\S+)\s+"host:\$stage/incoming/([^"]+)"\s*$',
            workflow, re.MULTILINE,
        )
        expected = {(name, name) for name in ASSETS}
        expected |= {("deploy.py", "deploy.py"), ("route.htaccess", ".htaccess")}
        self.assertEqual(len(transfers), len(expected), "duplicate/missing staging transfers")
        self.assertEqual(set(transfers), expected, "live staging and deploy.ASSETS differ")

    def test_asset_attribution_retains_all_three_authors_and_license(self):
        credits = (ROOT / "ASSET-CREDITS.md").read_text("utf-8")
        for source in (
            "sketchfab.com/3d-models/free-military-soldier-rigged-e9c56308a67d4a3db62e914fafa4d198",
            "sketchfab.com/3d-models/m24-bounty-hunter-sniper-rifle-d40e74e2259549f5b025807163f1028c",
            "sketchfab.com/3d-models/fps-arms-9452ce4cddde4110a4fd73e555a8e412",
            "creativecommons.org/licenses/by/4.0/",
        ):
            self.assertIn(source, credits)
        for creator in ("BAMEN", "Naudaff3D", "DJMaesen"):
            self.assertIn(creator, credits)
        self.assertIn("CC BY 4.0", credits)
        self.assertIn("Meshopt Decoder", credits)

    def test_payment_policy_remains_disabled(self):
        policy = (ROOT / "moj1-commerce-policy.mjs").read_text("utf-8")
        self.assertIn("checkoutEnabled:false", policy)
        self.assertIn("ownerApproved:false", policy)
        self.assertNotIn("tronWeb.trx.sendTransaction", policy)
        self.assertNotIn("window.tronLink.request", policy)


if __name__ == "__main__":
    unittest.main()
