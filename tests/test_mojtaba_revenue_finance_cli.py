"""Subprocess finance CLI acceptance: real calculations but no fabricated sales."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CMD=ROOT/"scripts/mojtaba_revenue_cli.py"
EXAMPLES=ROOT/"docs/revenue-p0"


def execute(*args):
    return subprocess.run([sys.executable,str(CMD),*map(str,args)],
                          capture_output=True,text=True,timeout=15)


class FinanceCommandTests(unittest.TestCase):
    def test_usd_margin_complete_cli(self):
        r=execute("--synthetic-margin",EXAMPLES/"mojtaba-synthetic-margin-usd.json")
        self.assertEqual(r.returncode,0,r.stderr)
        j=json.loads(r.stdout)
        self.assertEqual(j["gross_price_floor_synthetic"],"36.77")
        self.assertFalse(j["invoice_created"])

    def test_irr_margin_complete_cli(self):
        r=execute("--synthetic-margin",EXAMPLES/"mojtaba-synthetic-margin-irr.json")
        self.assertEqual(r.returncode,0,r.stderr)
        j=json.loads(r.stdout)
        self.assertEqual(j["gross_price_floor_synthetic"],"1500000")
        self.assertEqual(j["currency"],"IRR")

    def test_farm_end_to_end_has_real_correct_math(self):
        r=execute("--farm-analysis",EXAMPLES/"mojtaba-farm-break-even.synthetic.json")
        self.assertEqual(r.returncode,0,r.stderr)
        j=json.loads(r.stdout)
        self.assertEqual(j["estimated_profit_irr"],"500000000")
        self.assertEqual(j["breakeven_quantity_kg_ceil"],"5000")
        self.assertEqual(j["scenario_count"],27)
        self.assertEqual(j["period"],"annual")

    def test_non_synthetic_aggregate_is_allowed_but_unverified(self):
        sample=json.loads((EXAMPLES/"mojtaba-farm-break-even.synthetic.json").read_text())
        sample["synthetic_example"]=False
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"aggregate.json"
            p.write_text(json.dumps(sample))
            r=execute("--farm-analysis",p)
        self.assertEqual(r.returncode,0,r.stderr)
        j=json.loads(r.stdout)
        self.assertFalse(j["input_figures_independently_verified"])
        self.assertFalse(j["payment_collected"])
        self.assertFalse(j["synthetic_example"])

    def test_real_data_cannot_trigger_live_payment(self):
        p=EXAMPLES/"mojtaba-farm-break-even.synthetic.json"
        r=execute("--farm-analysis",p)
        j=json.loads(r.stdout)
        self.assertFalse(j["invoice_created"])
        self.assertFalse(j["production_deployed"])

    def test_local_private_file_is_new_0600(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"economic-review.json"
            p=EXAMPLES/"mojtaba-farm-break-even.synthetic.json"
            r=execute("--farm-analysis",p,"--output",out)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode),0o600)
            self.assertEqual(json.loads(out.read_text())["scenario_count"],27)

    def test_preserve_existing_financial_report(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"audit.json"
            out.write_text("DO_NOT_OVERWRITE",encoding="utf8")
            r=execute("--farm-analysis",
                 EXAMPLES/"mojtaba-farm-break-even.synthetic.json","--output",out)
            self.assertEqual(r.returncode,2)
            self.assertEqual(out.read_text(),"DO_NOT_OVERWRITE")

    def test_farm_unsupported_fields_fail_no_echo(self):
        with tempfile.TemporaryDirectory() as td:
            sample=json.loads((EXAMPLES/"mojtaba-farm-break-even.synthetic.json").read_text())
            sample["customer_email"]="PRIVATE@EXAMPLE.INVALID"
            p=Path(td)/"bad.json"
            p.write_text(json.dumps(sample))
            r=execute("--farm-analysis",p)
            self.assertEqual(r.returncode,2)
            self.assertNotIn("PRIVATE@EXAMPLE.INVALID",r.stderr+r.stdout)

    def test_noncanonical_bot_refused_in_cli(self):
        with tempfile.TemporaryDirectory() as td:
            sample=json.loads((EXAMPLES/"mojtaba-farm-break-even.synthetic.json").read_text())
            sample["canonical_bot"]="other.ai"
            p=Path(td)/"bad.json";p.write_text(json.dumps(sample))
            self.assertEqual(execute("--farm-analysis",p).returncode,2)

    def test_conflicting_cli_modes_are_rejected(self):
        r=execute("--farm-analysis",EXAMPLES/"mojtaba-farm-break-even.synthetic.json",
                  "--synthetic-margin",EXAMPLES/"mojtaba-synthetic-margin-usd.json")
        self.assertNotEqual(r.returncode,0)

    def test_bad_margin_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s=json.loads((EXAMPLES/"mojtaba-synthetic-margin-usd.json").read_text())
            s["currency"]="IRR"
            p=Path(td)/"bad.json";p.write_text(json.dumps(s))
            self.assertEqual(execute("--synthetic-margin",p).returncode,2)

    def test_no_trading_or_network_communication_in_modules(self):
        for name in ("mojtaba_farm_break_even.py", "mojtaba_revenue_margin.py"):
            source=(ROOT/"scripts"/name).read_text()
            for forbidden in ("import requests","from urllib.request",
                "import smtplib","import socket","openai.api","submit_order",
                "execute_trade","send_email","requests.post"):
                self.assertNotIn(forbidden,source)

if __name__=="__main__":unittest.main()
