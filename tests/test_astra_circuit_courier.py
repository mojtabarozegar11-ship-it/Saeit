"""Functional verification of the fourth original, offline Astra builder."""
from pathlib import Path
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/"product_prototypes"/"circuit_courier"
NODE=shutil.which("node")


class CircuitCourierTests(unittest.TestCase):
    def test_game_bundle_is_completely_offline(self):
        for name in ("engine.js","app.js","index.html","style.css","test_engine.js",
                     "self_test.py","README.md"):
            target=P/name
            self.assertTrue(target.is_file() and not target.is_symlink(),name)
            self.assertGreater(target.stat().st_size,100)
        html=(P/"index.html").read_text()
        self.assertIn('src="engine.js"',html)
        self.assertIn('src="app.js"',html)
        self.assertIn('href="style.css"',html)
        for dangerous in ("https://","http://","<iframe","<script src=\"https:"):
            self.assertNotIn(dangerous,html)
        self.assertIn('aria-live="polite"',html)
        self.assertIn('data-move="up"',html)
        self.assertNotIn("checkout",html.lower())

    @unittest.skipUnless(NODE,"Node.js unavailable on this platform")
    def test_all_36_puzzles_solvent_unique_and_exact_bfs_optimal(self):
        completed=subprocess.run(
            [NODE,str(P/"test_engine.js")],cwd=P,
            text=True,capture_output=True,timeout=30)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertIn("ASTRA_CIRCUIT_COURIER_36_VERIFIED_SOLVABLE=PASS",completed.stdout)
        self.assertIn("ASTRA_CIRCUIT_COURIER_NODE_TEST=PASS",completed.stdout)

    def test_independent_bundle_self_test_and_no_publishing_authority(self):
        completed=subprocess.run(
            [sys.executable,str(P/"self_test.py")],cwd=P,
            text=True,capture_output=True,timeout=30)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertIn("ASTRA_CIRCUIT_OFFLINE_BUNDLE_INTEGRITY=PASS",completed.stdout)
        self.assertIn("ASTRA_CIRCUIT_PRODUCT_SALE_READY=false",completed.stdout)

    def test_no_network_or_unsafe_source_expressions(self):
        engine=(P/"engine.js").read_text()
        app=(P/"app.js").read_text()
        for text in (engine,app):
            self.assertNotIn("XMLHttpRequest",text)
            self.assertNotIn("fetch(",text)
            self.assertNotIn("eval(",text)
            self.assertNotIn("new Function",text)
            self.assertNotIn("WebSocket",text)
            self.assertNotIn("Math.random(",text)
        self.assertIn("textContent",app)
        self.assertIn("localStorage",app)



if __name__=="__main__":
    unittest.main()
