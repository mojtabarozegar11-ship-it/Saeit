"""Regression tests proving quality critic rejects intentionally low-depth but valid software.

These tests assert REJECTIONS, not a high self-awarded quality score.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts/factory_f14_f28_product_quality_critic_20261021.py"
PROBE = ROOT / "scripts/factory_f14_keyboard_runtime_probe_20261021.js"
spec = importlib.util.spec_from_file_location("real_product_critic", AUDIT)
critic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(critic)


class RealQualityDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f14 = Path(os.environ.get("F14_PINNED_SOURCE_DIR",
                 str(ROOT))).resolve()
        cls.f28 = Path(os.environ.get("F28_PINNED_SOURCE_DIR",
                 str(ROOT))).resolve()
        cls.can_run = ((cls.f14 / "product_recipes/rootline_bloom_defense/game.js").exists()
                       and (cls.f28 / "product_recipes/greenhouse_crop_margin/"
                            "greenhouse_margin_lab_pilot.html").exists())

    def test_keyboard_runtime_probe_catches_real_missing_gameplay_action(self):
        if not self.can_run:
            self.skipTest("Pinned F14/F28 pilot checkouts required")
        proc = subprocess.run([
            "node", str(PROBE),
            str(self.f14 / "product_recipes/rootline_bloom_defense/engine.js"),
            str(self.f14 / "product_recipes/rootline_bloom_defense/game.js"),
        ], capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr[-1200:])
        observed = json.loads(proc.stdout)
        self.assertEqual(observed["observed_successful_keyboard_placements"], 0)
        self.assertGreaterEqual(observed["observed_successful_pointer_placements"], 1)
        self.assertEqual(observed["detection_positive_control"], "PASS")
        self.assertFalse(observed["keyboard_planting_supported"])

    def test_rejects_both_pilots_despite_green_1024x2_technical_tests(self):
        if not self.can_run:
            self.skipTest("Pinned F14/F28 pilot checkouts required")
        report = critic.assess(self.f14, self.f28, PROBE)
        self.assertEqual(report["aggregate_product_quality_verdict"],
                         "BLOCKED_REWORK_REQUIRED")
        self.assertFalse(report["release_authorized"])
        issues = {a["family"]: {item["code"] for item in a["issues"]}
                  for a in report["assessments"]}
        self.assertIn("F14_P0_KEYBOARD_PLANTING_MISSING", issues["F14"])
        self.assertIn("F14_P0_PLAYER_PLAYTESTS_UNVERIFIED", issues["F14"])
        self.assertIn("F14_P0_REAL_DEVICE_QUALITY_UNVERIFIED", issues["F14"])
        self.assertIn("F28_P0_NO_CROP_OR_SEASON_MODEL", issues["F28"])
        self.assertIn("F28_P0_RESOURCE_COST_DRIVERS_MISSING", issues["F28"])
        self.assertIn("F28_P0_UNCALIBRATED_MARKET_ASSUMPTIONS", issues["F28"])
        self.assertIn("F28_P0_SCHOLARLY_VALIDATION_NOT_VERIFIED", issues["F28"])
        for family in report["assessments"]:
            self.assertGreaterEqual(family["blocking_issue_count"], 5)
            self.assertFalse(family["commercial_ready"])
        for status_field in critic.RELEASE_FIELDS:
            self.assertIs(report[status_field], False)

    def test_enforcement_exit_code_prevents_false_green_release(self):
        if not self.can_run:
            self.skipTest("Pinned F14/F28 pilot checkouts required")
        with tempfile.TemporaryDirectory(prefix="quality-critic-test-") as d:
            out=Path(d)/"verdict.json"
            proc=subprocess.run([
                sys.executable,str(AUDIT),
                "--f14",str(self.f14),"--f28",str(self.f28),
                "--probe",str(PROBE),
                "--report",str(out),
                "--enforce",
            ],capture_output=True,text=True,timeout=25)
            self.assertEqual(proc.returncode, 2,proc.stderr)
            self.assertTrue(out.is_file())
            report=json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(report["release_authorized"])
            self.assertIn("FACTORY_PRODUCT_QUALITY_RELEASE_ALLOWED=0",proc.stdout)

if __name__=="__main__":
    unittest.main()
