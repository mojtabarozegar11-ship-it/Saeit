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

    def test_payment_policy_remains_disabled(self):
        policy = (ROOT / "moj1-commerce-policy.mjs").read_text("utf-8")
        self.assertIn("checkoutEnabled:false", policy)
        self.assertIn("ownerApproved:false", policy)
        self.assertNotIn("tronWeb.trx.sendTransaction", policy)
        self.assertNotIn("window.tronLink.request", policy)


if __name__ == "__main__":
    unittest.main()
