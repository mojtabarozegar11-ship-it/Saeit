"""End-to-end trustworthy worksheet rendering and private Markdown output."""
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from mojtaba_farm_review_report import render

EX=ROOT/"docs/revenue-p0/mojtaba-farm-break-even.synthetic.json"
CLI=ROOT/"scripts/mojtaba_revenue_cli.py"

def run(*args):
    return subprocess.run([sys.executable,str(CLI),*map(str,args)],
                          capture_output=True,text=True,timeout=15)

class Worksheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(EX.read_text("utf8"))

    def test_markdown_scientific_results(self):
        s=render(self.data)
        self.assertTrue(s.startswith("# برگه بررسی اقتصاد تولید"))
        self.assertIn("500000000",s)
        self.assertIn("5000",s)
        self.assertIn("150000",s)
        self.assertIn("نقطه سربه‌سر", (ROOT/"docs/revenue-p0/mojtaba-farm-economics-operator-manual.md").read_text())

    def test_sensitivity_contains_27_data_rows(self):
        s=render(self.data)
        rows=[line for line in s.splitlines() if line.startswith("| +") or line.startswith("| -")]
        self.assertEqual(len(rows),27)

    def test_example_provenance_is_explicit(self):
        s=render(self.data)
        self.assertIn("اعداد نمونهٔ ساختگی",s)
        self.assertIn("نه سفارش و نه درآمد وصول‌شده",s)

    def test_real_aggregate_is_flagged_unverified_not_mock(self):
        data={**self.data,"synthetic_example":False}
        s=render(data)
        self.assertIn("ارقام تجمیعی ارائه‌شده و هنوز راستی‌آزمایی‌نشده",s)
        self.assertNotIn("اعداد نمونهٔ ساختگی",s)

    def test_all_sections_present(self):
        s=render(self.data)
        for section in ("## نتایج پایه","## تحلیل حساسیت مستقل ۲۷ حالت",
                        "## گیت‌های صحت و تحویل","بدون دریافت وجه"):
            self.assertIn(section,s)

    def test_negative_contribution_explained(self):
        data={**self.data,"sale_price_irr_per_kg":"10000"}
        s=render(data)
        self.assertIn("هشدار اقتصادی",s)
        self.assertIn("محاسبه‌ناپذیر",s)

    def test_cli_prints_actual_markdown_not_json(self):
        r=run("--farm-report",EX)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(r.stdout.startswith("# برگه بررسی اقتصاد تولید"))
        self.assertNotIn('"schema":',r.stdout)

    def test_cli_writes_private_markdown_and_preserves_other_files(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"farm-review.md"
            p=run("--farm-report",EX,"--output",target)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
            self.assertIn("27",target.read_text())
            p=run("--farm-report",EX,"--output",target)
            self.assertEqual(p.returncode,2)
            self.assertIn("# برگه",target.read_text())

    def test_reject_customer_identity_from_report_input(self):
        with tempfile.TemporaryDirectory() as td:
            sample=dict(self.data,customer_name="PRIVATE_CLIENT")
            p=Path(td)/"private.json";p.write_text(json.dumps(sample))
            r=run("--farm-report",p)
            self.assertEqual(r.returncode,2)
            self.assertNotIn("PRIVATE_CLIENT",r.stdout+r.stderr)

    def test_no_contract_or_payment_created_by_document(self):
        s=render(self.data)
        self.assertIn("نه گزارش تأییدشده",s)
        self.assertIn("بدون شماره فاکتور",s)
        self.assertIn("بدون تحویل مشتری",s)

if __name__=="__main__":
    unittest.main()
