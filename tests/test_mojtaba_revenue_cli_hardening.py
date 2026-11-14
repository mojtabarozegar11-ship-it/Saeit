"""Real offline subprocess regression suite for the canonical 10-offer revenue CLI.

All cases are synthetic. No customer details, network, payments or deployment.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "mojtaba_revenue_cli.py"

def request(**updates):
    payload = dict(canonical_bot="mojtaba.bot.ai", offer_id="farm_economics",
                   scope_items=1, evidence_items=1, consent=True,
                   rights_documents=0, inventory_documents=0,
                   delivery_documents=0, synthetic_example=True)
    payload.update(updates)
    return payload

def run(*args):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                          capture_output=True, text=True, timeout=12)

class HardenedOneBotCliTests(unittest.TestCase):
    def test_qualified_synthetic_request_remains_inquiry_only(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";f.write_text(json.dumps(request()),encoding="utf-8")
            p=run("--qualify",f)
            self.assertEqual(p.returncode,0,p.stderr)
            o=json.loads(p.stdout)
            self.assertEqual(o["canonical_bot"],"mojtaba.bot.ai")
            self.assertEqual(o["order_state"],"inquiry_only")
            self.assertFalse(o["payment_verified"])
            self.assertIsNone(o["collected_revenue"])

    def test_duplicate_consent_false_true_denied(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text(json.dumps(request()).replace('"consent": true',
                '"consent": false, "consent": true'),encoding="utf-8")
            self.assertEqual(run("--qualify",f).returncode,2)

    def test_duplicate_synthetic_false_true_denied(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text(json.dumps(request()).replace('"synthetic_example": true',
                '"synthetic_example": false, "synthetic_example": true'),encoding="utf-8")
            self.assertEqual(run("--qualify",f).returncode,2)

    def test_duplicate_offer_id_prevents_cross_model_misroute(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text(json.dumps(request()).replace('"offer_id": "farm_economics"',
                '"offer_id": "game_license", "offer_id": "farm_economics"'),encoding="utf-8")
            self.assertEqual(run("--qualify",f).returncode,2)

    def test_nested_duplicate_key_denied_in_kpi(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text('{"views":10,"inquiries":2,"qualified":1,"approved_quotes":0,'
                '"paid_orders":0,"delivered_orders":0,"synthetic_example":true,'
                '"junk":{"a":1,"a":2}}',encoding="utf-8")
            self.assertEqual(run("--synthetic-kpis",f).returncode,2)

    def test_nan_count_not_converted_into_valid_customer_metric(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text('{"views":NaN,"inquiries":0,"qualified":0,'
                '"approved_quotes":0,"paid_orders":0,"delivered_orders":0,'
                '"synthetic_example":true}',encoding="utf-8")
            self.assertEqual(run("--synthetic-kpis",f).returncode,2)

    def test_infinite_count_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json"
            f.write_text(json.dumps(request()).replace('"scope_items": 1',
                '"scope_items": Infinity'),encoding="utf-8")
            self.assertEqual(run("--qualify",f).returncode,2)

    def test_file_symlink_denied(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";f.write_text(json.dumps(request()),encoding="utf-8")
            link=Path(d)/"alias";link.symlink_to(f)
            self.assertEqual(run("--qualify",link).returncode,2)

    def test_fifo_denied_without_blocking(self):
        if not hasattr(os,"mkfifo"):
            self.skipTest("FIFO unavailable")
        with tempfile.TemporaryDirectory() as d:
            pipe=Path(d)/"in_fifo";os.mkfifo(pipe)
            self.assertEqual(run("--qualify",pipe).returncode,2)

    def test_directory_denied(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run("--qualify",d).returncode,2)

    def test_non_utf8_not_echoed(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";f.write_bytes(b"\xffSECRET")
            p=run("--qualify",f)
            self.assertEqual(p.returncode,2)
            self.assertNotIn("SECRET",p.stderr+p.stdout)

    def test_32769_byte_limit_still_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";f.write_bytes(b" " * 32769)
            self.assertEqual(run("--qualify",f).returncode,2)

    def test_32768_byte_valid_json_with_whitespace_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";raw=json.dumps(request()).encode("utf-8")
            f.write_bytes(raw + b" "*(32768-len(raw)))
            self.assertEqual(run("--qualify",f).returncode,0)

    def test_file_same_as_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";raw=json.dumps(request())
            f.write_text(raw,encoding="utf-8")
            self.assertEqual(run("--qualify",f,"--output",f).returncode,2)
            self.assertEqual(f.read_text(encoding="utf-8"),raw)

    def test_existing_report_never_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";out=Path(d)/"report.json"
            f.write_text(json.dumps(request()));out.write_text("PRESERVE",encoding="utf-8")
            self.assertEqual(run("--qualify",f,"--output",out).returncode,2)
            self.assertEqual(out.read_text(encoding="utf-8"),"PRESERVE")

    def test_symlinked_output_never_replaces_target(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";victim=Path(d)/"existing";out=Path(d)/"alias"
            f.write_text(json.dumps(request()));victim.write_text("SAVED")
            out.symlink_to(victim)
            self.assertEqual(run("--qualify",f,"--output",out).returncode,2)
            self.assertEqual(victim.read_text(),"SAVED")

    def test_output_parent_symlink_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);actual=root/"real";actual.mkdir()
            linked=root/"aliased";linked.symlink_to(actual,target_is_directory=True)
            f=root/"in.json";f.write_text(json.dumps(request()))
            self.assertEqual(run("--qualify",f,"--output",linked/"report.json").returncode,2)
            self.assertFalse((actual/"report.json").exists())

    def test_new_report_private_no_cash_claim(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";out=Path(d)/"out.json"
            f.write_text(json.dumps(request()))
            p=run("--qualify",f,"--output",out)
            self.assertEqual(p.returncode,0,p.stderr)
            if os.name=="posix":
                self.assertEqual(stat.S_IMODE(out.stat().st_mode),0o600)
            o=json.loads(out.read_text())
            self.assertEqual(o["order_state"],"inquiry_only")
            self.assertIsNone(o["collected_revenue"])
            self.assertFalse(o["auto_send"])

    def test_rejects_email_and_keeps_it_out_of_error(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"in.json";f.write_text(json.dumps(request(email="secret@example.invalid")))
            p=run("--qualify",f)
            self.assertEqual(p.returncode,2)
            self.assertNotIn("secret@example.invalid",p.stderr+p.stdout)

    def test_catalog_shows_only_one_bot_and_no_actual_money(self):
        p=run("--catalog")
        self.assertEqual(p.returncode,0,p.stderr)
        o=json.loads(p.stdout)
        self.assertEqual(o["canonical_bot"],"mojtaba.bot.ai")
        self.assertEqual(len(o["offers"]),10)
        self.assertIsNone(o["actual_revenue"])
        self.assertFalse(o["deployed"])

    def test_synthetic_zero_denominators_are_null(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"kpi.json";f.write_text(json.dumps(dict(
                views=0,inquiries=0,qualified=0,approved_quotes=0,
                paid_orders=0,delivered_orders=0,synthetic_example=True)))
            p=run("--synthetic-kpis",f)
            self.assertEqual(p.returncode,0,p.stderr)
            o=json.loads(p.stdout)
            self.assertIsNone(o["inquiry_rate"])
            self.assertIsNone(o["actual_revenue"])

    def test_real_cash_funnel_is_never_accepted_as_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"kpi.json";f.write_text(json.dumps(dict(
                views=2,inquiries=1,qualified=1,approved_quotes=1,
                paid_orders=1,delivered_orders=1,synthetic_example=False)))
            self.assertEqual(run("--synthetic-kpis",f).returncode,2)

if __name__=="__main__":
    unittest.main()
