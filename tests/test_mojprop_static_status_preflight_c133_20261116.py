"""Moj Prop static-release preflight must parse and fail closed before publishing.

Source-only checks; no workflow dispatch, cPanel/VPS/DB, customer POST or cost.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mojplaywin-moj-prop-deploy.yml"
INSTALLER = ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py"
REQUIRED = (
    "core/mojprop_catalog_contract.py",
    "core/mojprop_offer_draft.py",
    "core/mojprop_workflow.py",
)


def status_preflight():
    src = WORKFLOW.read_text(encoding="utf-8")
    start = src.index('      - name: Verify private status receipt API exists')
    end = src.find('      - name:', start + 10)
    return src[start:end if end >= 0 else None]


class StatusPreflightReleaseTests(unittest.TestCase):
    def test_curl_shell_continuations_are_single_not_escaped_backslashes(self):
        text = status_preflight()
        lines = text.splitlines()
        pieces = [
            line for line in lines
            if ('code="$(curl' in line and "max-time 20" in line)
            or ("-H 'Accept: application/json'" in line
                and "mojprop-status-preflight.json" in line)
        ]
        self.assertEqual(len(pieces), 2)
        for part in pieces:
            self.assertTrue(part.rstrip().endswith("\\"))
            self.assertFalse(part.rstrip().endswith("\\\\"))
        self.assertIn("-w '%{http_code}' 'https://mojplaywin.com/moj-prop-status/'", text)

    def test_json_error_contract_must_fail_closed_before_static_publication(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("MOJPROP_STATUS_API_NOT_READY", status_preflight())
        self.assertIn("Receipt invalid or expired", status_preflight())
        self.assertIn("Receipt API contract missing; abort static publication", status_preflight())
        self.assertLess(
            src.index("      - name: Verify private status receipt API exists"),
            src.index("      - name: Update", src.index("      - name: Verify private status receipt API exists")),
        )

    def test_dependent_module_changes_trigger_both_source_workflows(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        for name in REQUIRED:
            self.assertEqual(src.count('      - "' + name + '"'), 2)

    def test_validator_compiles_imported_dependencies_before_dispatch(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        command = src.split("python3 -m py_compile ", 1)[1].split("\n", 1)[0]
        for name in REQUIRED:
            self.assertIn(name, command)

    def test_backend_staging_carries_needed_imports_not_just_api_view(self):
        src = INSTALLER.read_text(encoding="utf-8")
        tree = ast.parse(src)
        files = next(
            x.value for x in tree.body
            if isinstance(x, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "FILES" for t in x.targets)
        )
        names = set()
        for node in files.elts:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path":
                names.add(ast.literal_eval(node.args[0]))
        for name in REQUIRED:
            self.assertIn(name, names)
        self.assertIn("REPLACE_FILES = tuple(path for path in FILES", src)
        exceptions = src.split("REPLACE_FILES = tuple(path for path in FILES", 1)[1].split("\n\n",1)[0]
        for name in REQUIRED:
            self.assertNotIn(name, exceptions)

    def test_no_merge_push_or_raw_pr_can_trigger_live_deploy(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event_name == 'workflow_dispatch'", src)
        self.assertIn("MOJPROP_FULL_DB_APP_MEDIA_RESTORE_VERIFIED", src)
        self.assertIn("MOJPROP_PASSENGER_TENANT_ISOLATION_VERIFIED", src)
        self.assertIn("MOJPROP_STATIC_APPROVED_MAIN_SHA == github.sha", src)
        self.assertIn("inputs.owner_approved_static_release == true", src)


if __name__ == "__main__":
    unittest.main()
