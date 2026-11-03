#!/usr/bin/env python3
"""Fail closed if the release workflow omits an asset required by the game.

Offline only: this test never opens an SSH connection or writes to production.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'games' / 'ramadan-war'
WORKFLOW = ROOT / '.github' / 'workflows' / 'zomorod-ramadan-war-web-card.yml'


def manifest_assets():
    source = (GAME / 'deploy.py').read_text(encoding='utf-8')
    match = re.search(r'^ASSETS=(\[[^\n]+\])$', source, re.M)
    if not match:
        raise AssertionError('deploy.py must have an explicit static ASSETS list')
    return ast.literal_eval(match.group(1))


def transfer_map():
    workflow = WORKFLOW.read_text(encoding='utf-8')
    return re.findall(
        r'^\s*timeout\s+\d+s\s+scp\s+-q\s+-F\s+"\$d/config"\s+'
        r'games/ramadan-war/([^\s"]+)\s+"host:\$stage/incoming/([^"]+)"',
        workflow, re.M
    )


class ReleaseTransferContract(unittest.TestCase):
    def test_every_manifest_asset_is_staged_once_at_same_path(self):
        assets = manifest_assets()
        self.assertEqual(len(assets), len(set(assets)), 'duplicate manifest asset')
        transfers = transfer_map()
        expected = {(asset, asset) for asset in assets}
        expected |= {('deploy.py', 'deploy.py'), ('route.htaccess', '.htaccess')}
        self.assertEqual(len(transfers), len(set(transfers)), 'duplicate stage transfer')
        self.assertEqual(set(transfers), expected,
                         'release would omit, rename or unexpectedly stage a game file')

    def test_all_imported_runtime_modules_are_manifested(self):
        source = (GAME / 'game.js').read_text(encoding='utf-8')
        imports = re.findall(r"from\s+['\"]\./([^'\"]+\.mjs)['\"]", source)
        self.assertGreaterEqual(len(imports), 6)
        assets = set(manifest_assets())
        self.assertTrue(set(imports).issubset(assets),
                        'game imports an MJS module absent from release manifest')
        for module in imports:
            self.assertTrue((GAME / module).is_file(), 'missing runtime module: ' + module)

    def test_no_unapproved_push_can_trigger_live_deploy(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn("contains(github.event.head_commit.message, '[approved-zm-ramadan-card-live-20261022]')", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn('cancel-in-progress: false', workflow)


    def test_disk_gate_precedes_any_cpanel_release_staging(self):
        workflow = WORKFLOW.read_text(encoding='utf-8')
        guard = 'Refuse insufficient cPanel capacity before creating any release stage'
        stage = 'Transfer the replacement web client and scoped updater to private staging'
        self.assertIn(guard, workflow)
        self.assertIn('games/ramadan-war/release_storage_guard.py', workflow)
        self.assertLess(workflow.index(guard), workflow.index(stage),
                        'release must fail closed before any stage mkdir or scp')
        qa = (ROOT / '.github/workflows/zomorod-ramadan-war-model-qa.yml').read_text('utf-8')
        self.assertIn('test_release_storage_guard.py', qa)


if __name__ == '__main__':
    unittest.main()
