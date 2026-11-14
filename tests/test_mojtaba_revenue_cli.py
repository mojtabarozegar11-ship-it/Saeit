"""Real subprocess tests for the single-bot offline commercial command."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "scripts/mojtaba_revenue_cli.py"

def run(*args):
    return subprocess.run([sys.executable, str(PROGRAM), *map(str,args)],
                          capture_output=True, text=True, timeout=12)

def intake(**overrides):
    x = {"canonical_bot":"mojtaba.bot.ai", "offer_id":"farm_economics",
         "scope_items":1, "evidence_items":1, "consent":True,
         "rights_documents":0, "inventory_documents":0,
         "delivery_documents":0,"synthetic_example":True}
    x.update(overrides)
    return x

class OfflineCliTests(unittest.TestCase):
    def test_catalog_lists_ten_only_under_canonical_identity(self):
        r=run("--catalog")
        self.assertEqual(r.returncode,0,r.stderr)
        x=json.loads(r.stdout)
        self.assertEqual(x["canonical_bot"],"mojtaba.bot.ai")
        self.assertEqual(len(x["offers"]),10)
        self.assertFalse(x["deployed"])
        self.assertIsNone(x["actual_revenue"])

    def test_catalog_does_not_allow_disk_export(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"catalog.json"
            r=run("--catalog","--output",p)
            self.assertEqual(r.returncode,2)
            self.assertFalse(p.exists())

    def test_default_no_arg_fails(self):
        self.assertNotEqual(run().returncode,0)

    def test_offline_qualification_success(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"input.json"
            p.write_text(json.dumps(intake()),encoding="utf8")
            r=run("--qualify",p)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)["order_state"],"inquiry_only")

    def test_output_is_private_new_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json";o=Path(t)/"out.json"
            p.write_text(json.dumps(intake()),encoding="utf8")
            r=run("--qualify",p,"--output",o)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(stat.S_IMODE(o.stat().st_mode),0o600)
            self.assertIsNone(json.loads(o.read_text())["collected_revenue"])

    def test_overwrite_refused_and_existing_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json";o=Path(t)/"out.json"
            p.write_text(json.dumps(intake()),encoding="utf8")
            o.write_text("DO NOT DELETE",encoding="utf8")
            r=run("--qualify",p,"--output",o)
            self.assertEqual(r.returncode,2)
            self.assertEqual(o.read_text(),"DO NOT DELETE")

    def test_input_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json"
            v=json.dumps(intake());p.write_text(v,encoding="utf8")
            r=run("--qualify",p,"--output",p)
            self.assertEqual(r.returncode,2)
            self.assertEqual(p.read_text(),v)

    def test_input_symlink_refused(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json";q=Path(t)/"alias.json"
            p.write_text(json.dumps(intake()))
            q.symlink_to(p)
            r=run("--qualify",q)
            self.assertEqual(r.returncode,2)

    def test_output_symlink_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json";v=Path(t)/"protected";o=Path(t)/"out.json"
            p.write_text(json.dumps(intake()));v.write_text("UNTOUCHED")
            o.symlink_to(v)
            r=run("--qualify",p,"--output",o)
            self.assertEqual(r.returncode,2)
            self.assertEqual(v.read_text(),"UNTOUCHED")

    def test_invalid_customer_pii_does_not_echo(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"in.json"
            p.write_text(json.dumps(intake(email="SECRET-CUSTOMER-ADDRESS")))
            r=run("--qualify",p)
            self.assertEqual(r.returncode,2)
            self.assertNotIn("SECRET-CUSTOMER-ADDRESS",r.stdout+r.stderr)

    def test_large_input_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"large.json";p.write_text("X"*33000)
            self.assertEqual(run("--qualify",p).returncode,2)

    def test_bad_json_blocked_without_content_echo(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"bad.json";p.write_text('{token: PRIVATE}')
            r=run("--qualify",p)
            self.assertEqual(r.returncode,2)
            self.assertNotIn("PRIVATE",r.stdout+r.stderr)

    def test_synthetic_kpi_ratios(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"kpi.json"
            p.write_text(json.dumps(dict(views=10,inquiries=3,qualified=2,
                approved_quotes=1,paid_orders=0,delivered_orders=0,
                synthetic_example=True)))
            r=run("--synthetic-kpis",p)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)["inquiry_rate"],"0.3000")

    def test_non_synthetic_kpi_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"kpi.json"
            p.write_text(json.dumps(dict(views=10,inquiries=3,qualified=2,
                approved_quotes=1,paid_orders=0,delivered_orders=0,
                synthetic_example=False)))
            r=run("--synthetic-kpis",p)
            self.assertEqual(r.returncode,2)

    def test_network_not_imported_by_cli(self):
        s=PROGRAM.read_text("utf8")
        for banned in ("requests", "urllib.request", "smtplib", "subprocess.run",
                       "websocket", "broker_sdk", "payment_intent"):
            self.assertNotIn(banned,s)

if __name__=="__main__":
    unittest.main()
