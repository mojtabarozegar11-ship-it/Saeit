"""No global template, URL rewrites, Passenger restarts or protected child files."""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/mpw_footer_exact_mainonly_patch_20261018.py"

class FooterMainOnlySafetyTest(unittest.TestCase):
    def test_patch_selftest(self):
        r=subprocess.run([sys.executable,str(SOURCE),"selftest"],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn("SELFTEST=PASS",r.stdout)
    def test_exact_owner_allowlist(self):
        spec=importlib.util.spec_from_file_location("safe_mpw_footer",SOURCE)
        m=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertEqual(len(m.STATIC),19)
        self.assertEqual(len(m.APP_SHA),2)
        self.assertEqual(len(set(m.STATIC)),19)
        self.assertTrue(all(len(sha)==64 for sha in (*m.STATIC.values(),*m.APP_SHA.values())))
        self.assertTrue(all(name.endswith(".html")==False for name in m.STATIC))
        self.assertNotIn("base.html",m.APP_SHA)
        self.assertTrue(all("mojplaywin" in path for path in m.APP_SHA))
        self.assertEqual(len(list(m.candidates())),21)
    def test_fail_closed_code_and_rollback(self):
        s=SOURCE.read_text()
        for token in ("Concurrent edit","Route mismatch","Rollback conflict","os.replace","Passenger","FOOTER_ATOMIC_INSTALLED"):
            self.assertIn(token,s)
        self.assertNotIn("subprocess.",s)
        self.assertNotIn("shutil.rmtree",s)
    def test_prod_workflow_approval_and_exact_protection(self):
        w=(ROOT/".github/workflows/mpw-footer-exact-mainonly-live-20261018.yml").read_text()
        self.assertEqual(w.count("\n    steps:"),1)
        for marker in ("approved-mpw-mainonly-footer-20261018","PROTECTED_SUBSITE_CHANGED","rollback","SSH","mpw_footer_exact_mainonly_patch_20261018.py"):
            self.assertIn(marker,w)

if __name__=="__main__":unittest.main()
