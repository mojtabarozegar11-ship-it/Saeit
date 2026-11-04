#!/usr/bin/env python3
"""The R58 production preflight must match its 36-file delivery manifest."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class CurrentReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / 'deploy.py').read_text('utf-8')
        match = re.search(r'^ASSETS=(\[[^\n]+\])$', self.source, re.M)
        self.assertIsNotNone(match)
        self.assets = set(ast.literal_eval(match.group(1)))

    def test_all_literal_release_file_lookups_are_manifested(self):
        looked_up = set(re.findall(r"""new\[['"]([^'"]+)['"]\]""", self.source))
        self.assertFalse(looked_up - self.assets, 'preflight references deleted assets')

    def test_excluded_m24_and_arm_textures_are_not_required(self):
        for name in ('m24-sniper-ccby.glb', 'arms_basecolor.webp', 'arms_normal.webp'):
            self.assertNotIn(name, self.assets)
            self.assertNotIn("new['" + name + "']", self.source)

    def test_verified_soldier_and_procedural_rifle_are_required(self):
        self.assertIn('b00ed33108f2579880c82cd27d10f9237ff3a219', self.source)
        self.assertIn('self-authored procedural rifle', self.source)
        self.assertIn('soldier-rigged-ccby.glb', self.assets)

    def test_optional_2d_entrance_is_in_published_package(self):
        self.assertIn('low-graphics.html', self.assets)
        self.assertIn('href="./low-graphics.html"', self.source)
        self.assertIn("canvas.getContext('2d')", self.source)


if __name__ == '__main__':
    unittest.main()
