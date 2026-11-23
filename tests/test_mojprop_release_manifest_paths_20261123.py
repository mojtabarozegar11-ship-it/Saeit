"""Regression guard for Moj Prop release tuple paths.

A literal backslash-n in the FILES comment previously hid two required
Path entries on the same physical comment line. Parsing the Python AST
instead of searching raw text prevents a false positive.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py"
WORKFLOW = ROOT / ".github/workflows/mojprop-backend-controlled-release-20261115.yml"

class MojPropReleaseManifestTests(unittest.TestCase):
    def test_required_modules_are_real_path_expressions(self):
        tree = ast.parse(INSTALLER.read_text(encoding="utf-8"))
        assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "FILES"
                    for target in node.targets)
        )
        self.assertIsInstance(assignment.value, ast.Tuple)
        entries = [
            ast.literal_eval(item.args[0])
            for item in assignment.value.elts
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == "Path"
            and len(item.args) == 1
        ]
        for required in ("templates/moj-prop/payment/index.html", "core/models.py"):
            with self.subTest(required=required):
                self.assertEqual(entries.count(required), 1)
        self.assertEqual(len(entries), len(assignment.value.elts))

    def test_archive_also_includes_payment_template(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("templates/moj-prop/payment/index.html", workflow)
        self.assertIn("scripts/deploy_mojplaywin_moj_prop_backend.py", workflow)

if __name__ == "__main__":
    unittest.main()
