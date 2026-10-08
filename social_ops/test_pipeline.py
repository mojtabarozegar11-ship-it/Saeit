"""Offline checks for the three-brand editorial pipeline."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ThreeBrandPipelineTests(unittest.TestCase):
    def test_registry(self):
        data = json.loads((ROOT / "social_ops/brands.json").read_text(encoding="utf-8"))
        brands = data["brands"]
        self.assertEqual({b["id"] for b in brands}, {"personal", "company", "mojplaywin"})
        self.assertEqual(len({b["id"] for b in brands}), len(brands))
        self.assertEqual(data["policy"]["publishing"], "disabled_until_platform_connection_and_approval")

    def test_drafts_are_isolated_and_not_published(self):
        subprocess.run([sys.executable, "social_ops/generate.py"], cwd=ROOT, check=True)
        for brand in ("personal", "company", "mojplaywin"):
            path = ROOT / "social_ops/output" / f"{brand}_drafts.json"
            items = json.loads(path.read_text(encoding="utf-8"))
            self.assertGreater(len(items), 0)
            self.assertTrue(all(x["brand"] == brand for x in items))
            self.assertTrue(all(x["status"] == "draft_requires_review" for x in items))
            self.assertEqual(len({x["id"] for x in items}), len(items))

if __name__ == "__main__":
    unittest.main()
