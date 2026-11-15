"""Regression guards for the Moj Prop isolated backend release boundary.

These tests are source-level only: they never contact the production host,
deploy, send mail, or create a customer request.
"""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy_mojplaywin_moj_prop_backend.py"
WORKFLOW = ROOT / ".github" / "workflows" / "mojplaywin-moj-prop-deploy.yml"
DEPENDENCIES = {
    "core/mojprop_catalog_contract.py",
    "core/mojprop_offer_draft.py",
    "core/mojprop_workflow.py",
}


class MojPropReleaseDependencyContractTests(unittest.TestCase):
    def test_backend_dependencies_are_backed_up_and_staged(self):
        tree = ast.parse(DEPLOY.read_text(encoding="utf-8"))
        tuples = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {"FILES", "REPLACE_FILES"}:
                    values = set()
                    if isinstance(node.value, ast.Tuple):
                        for item in node.value.elts:
                            if (
                                isinstance(item, ast.Call)
                                and isinstance(item.func, ast.Name)
                                and item.func.id == "Path"
                                and len(item.args) == 1
                                and isinstance(item.args[0], ast.Constant)
                            ):
                                values.add(item.args[0].value)
                    tuples[target.id] = values
        self.assertTrue(DEPENDENCIES <= tuples["FILES"])
        self.assertTrue(DEPENDENCIES <= tuples["REPLACE_FILES"])

    def test_workflow_triggers_and_compiles_dependencies(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for path in DEPENDENCIES:
            self.assertGreaterEqual(text.count(f'"{path}"'), 2)
            self.assertIn(path, text.split("python3 -m py_compile ", 1)[1])
        self.assertIn(
            'curl --silent --show-error --max-redirs 0 --connect-timeout 10 --max-time 20 \\\n',
            text,
        )
        self.assertNotIn(
            'curl --silent --show-error --max-redirs 0 --connect-timeout 10 --max-time 20 \\\\\n',
            text,
        )


if __name__ == "__main__":
    unittest.main()
