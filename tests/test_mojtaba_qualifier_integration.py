"""Direct execution of the established two-offer CLI with the strict reader/writer."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "revenue_dual_offer_qualifier.py"


def sample(**options):
    entry = {"offer": "website_checkout_repair", "package": "diagnosis",
             "scope_items": 1, "evidence_items": 2, "consent_to_contact": True,
             "inputs_available": True, "synthetic_example": True}
    entry.update(options)
    return entry


class QualifierIntegrationTests(unittest.TestCase):
    def invoke(self, src, out=None):
        cmd = [sys.executable, str(SCRIPT), str(src)]
        if out is not None:
            cmd.extend(["--output", str(out)])
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_checkout_qualifies_only_for_manual_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json"; f.write_text(json.dumps(sample()))
            p=self.invoke(f)
            self.assertEqual(p.returncode,0,p.stderr)
            value=json.loads(p.stdout)
            self.assertEqual(value["qualification"],"manual_quote_review")
            self.assertEqual(value["canonical_bot"],"mojtaba.bot.ai")
            self.assertEqual(value["order_state"],"inquiry_only")
            self.assertEqual(value["payment_state"],"not_requested")
            self.assertFalse(value["auto_send_enabled"])

    def test_farm_offer_has_no_fabricated_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_text(json.dumps(sample(offer="farm_break_even",package="analysis")))
            p=self.invoke(f)
            self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads(p.stdout)
            self.assertIsNone(r["price_band_non_binding"])
            self.assertIn("local_price_not_approved",r["blockers"])

    def test_nonconsent_does_not_qualify(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_text(json.dumps(sample(consent_to_contact=False)))
            p=self.invoke(f)
            self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads(p.stdout)
            self.assertIn("contact_consent_missing",r["blockers"])
            self.assertEqual(r["qualification"],"needs_more_information")

    def test_input_symlink_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"src";src.write_text(json.dumps(sample()))
            l=Path(tmp)/"l";l.symlink_to(src)
            p=self.invoke(l)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("intake symlink rejected",p.stderr)

    def test_duplicate_consent_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";raw=json.dumps(sample())
            f.write_text(raw.replace('"consent_to_contact": true', '"consent_to_contact": false, "consent_to_contact": true'))
            p=self.invoke(f)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("ambiguous JSON intake",p.stderr)

    def test_nan_input_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_text(json.dumps(sample(evidence_items=float("nan"))))
            p=self.invoke(f)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("ambiguous JSON intake",p.stderr)

    def test_no_existing_report_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp=Path(tmp)/"in";out=Path(tmp)/"out"
            inp.write_text(json.dumps(sample()));out.write_text("DO NOT CHANGE")
            p=self.invoke(inp,out)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual(out.read_text(),"DO NOT CHANGE")

    def test_private_output_is_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp=Path(tmp)/"in";out=Path(tmp)/"out"
            inp.write_text(json.dumps(sample()))
            p=self.invoke(inp,out)
            self.assertEqual(p.returncode,0,p.stderr)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(out.stat().st_mode)&0o077,0)
            result=json.loads(out.read_text())
            self.assertNotIn("email",result)
            self.assertFalse(result["personal_data_exported"])
            self.assertEqual(result["delivery_state"],"not_delivered")

    def test_extra_personal_data_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_text(json.dumps(sample(email="secret@example.invalid")))
            p=self.invoke(f)
            self.assertNotEqual(p.returncode,0)
            self.assertNotIn("secret@example.invalid",p.stderr)

    def test_input_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";txt=json.dumps(sample());f.write_text(txt)
            p=self.invoke(f,f)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual(f.read_text(),txt)

    def test_cross_offer_package_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_text(json.dumps(sample(offer="farm_break_even",package="diagnosis")))
            p=self.invoke(f)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("unsupported package",p.stderr)

    def test_more_than_64kb_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/"in.json";f.write_bytes(b" "*65537)
            p=self.invoke(f)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("64 KiB",p.stderr)

if __name__ == "__main__": unittest.main()
