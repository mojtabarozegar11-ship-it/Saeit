"""Regression for surgical in-place Zomorod native storefront patcher."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("zm_store_patcher",ROOT / "scripts/zomorod_store_live_harden_20261026.py")
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)
INDEX = ROOT / "content/zomorod-v11/store_index.php"

class TestSurgicalStore(unittest.TestCase):
    def test_candidate_preserves_payment_and_digital_catalog(self):
        original = INDEX.read_text(encoding="utf-8")
        candidate=PATCH.prepare(original)
        self.assertIn(PATCH.MARK,candidate)
        self.assertIn("free_digital_products WHERE enabled=1",candidate)
        self.assertIn("foreach($free as $p)",candidate)
        self.assertIn("foreach($items as $p)",candidate)
        self.assertIn("پرداخت بانک شهر",candidate)
        self.assertIn("Content-Security-Policy",candidate)
        self.assertIn("https://zomorodmelal.ir/store/",candidate)
        self.assertIn("#main-content",candidate)
        self.assertNotIn("curl_exec(",candidate)
        with self.assertRaisesRegex(RuntimeError,"ALREADY_PATCHED"):
            PATCH.prepare(candidate)

    def test_unknown_template_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"UNKNOWN_ZOMOROD_STOREFRONT"):
            PATCH.prepare("<?php echo 'other site';")

    def test_missing_anchor_rejected(self):
        body=INDEX.read_text(encoding="utf-8").replace("header('X-Content-Type-Options: nosniff');","")
        with self.assertRaisesRegex(RuntimeError,"ANCHOR_NOT_UNIQUE_OR_ABSENT"):
            PATCH.prepare(body)

    @unittest.skipUnless(shutil.which("php"),"PHP CLI required")
    def test_candidate_php_lint(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"index.php"
            file.write_text(PATCH.prepare(INDEX.read_text(encoding="utf8")),encoding="utf8")
            result=subprocess.run(["php","-l",str(file)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=="__main__":
    unittest.main()
