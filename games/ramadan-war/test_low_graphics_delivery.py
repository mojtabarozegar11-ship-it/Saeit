#!/usr/bin/env python3
"""WebGL-free mode is an explicitly selected, self-contained, isolated game."""
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parent.parent

class LowGraphicsDeliveryContract(unittest.TestCase):
    def test_optional_link_is_visible_and_relative(self):
        html = (ROOT / 'index.html').read_text('utf-8')
        self.assertIn('href="./low-graphics.html"', html)
        self.assertIn('class="lowgraphics-link"', html)
        self.assertIn('id="graphicsStartWarning"', html)
        self.assertNotIn('window.location.replace', html)

    def test_standalone_requires_no_webgl_or_remote_assets(self):
        html = (ROOT / 'low-graphics.html').read_text('utf-8')
        self.assertIn('<canvas id="battle"', html)
        self.assertIn("canvas.getContext('2d')", html)
        self.assertNotIn('getContext(\'webgl', html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('<link rel="stylesheet"', html)
        self.assertNotIn('fetch(', html)
        self.assertNotIn('https://', html)
        self.assertNotIn('http://', html)

    def test_save_is_separate_and_payment_disabled(self):
        html = (ROOT / 'low-graphics.html').read_text('utf-8')
        self.assertIn("KEY='ramadan-war-r58-lowgraphics-save-v1'", html)
        self.assertNotIn("rwNativeCampaign", html)
        self.assertIn("format:'RW-R58-LOWGRAPHICS'", html)
        self.assertIn('پیشرفت دو حالت به یکدیگر تبدیل نمی‌شود', html)
        self.assertIn('بدون پرداخت یا اتصال کیف پول', html)

    def test_deploy_and_stage_include_optional_file_once(self):
        source = (ROOT / 'deploy.py').read_text('utf-8')
        match = re.search(r'^ASSETS=(\[[^\n]+\])$', source, re.M)
        self.assertIsNotNone(match)
        assets = ast.literal_eval(match.group(1))
        self.assertEqual(assets.count('low-graphics.html'), 1)
        workflow = (REPOSITORY / '.github/workflows/zomorod-ramadan-war-web-card.yml').read_text('utf-8')
        transfer = 'games/ramadan-war/low-graphics.html "host:$stage/incoming/low-graphics.html"'
        self.assertEqual(workflow.count(transfer), 1)
        self.assertIn('[approved-zm-ramadan-card-live-20261022]', workflow)

if __name__ == '__main__':
    unittest.main()
