"""Real dry-run quote review tests; never authorizes a buyer transaction."""
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import revenue_cycle2_quote as q


def sample(code="website_diagnosis", **change):
    values = dict(canonical_bot="mojtaba.bot.ai", offer_id=code,
                  scope_items=1, evidence_items=1, consent=True,
                  rights_documents=0, inventory_documents=0,
                  delivery_documents=0, synthetic_example=True,
                  work_package=q.PACKAGES[code][0])
    values.update(change)
    return values


class QuotePacketTests(unittest.TestCase):
    def test_all_ten_packages_have_review_packets(self):
        for code in q.PACKAGES:
            with self.subTest(code=code):
                packet = q.generate(sample(code))
                self.assertEqual(packet["canonical_bot"], "mojtaba.bot.ai")
                self.assertFalse(packet["quote_sent"])
                self.assertFalse(packet["payment_verified"])
                self.assertFalse(packet["delivery_verified"])
                self.assertFalse(packet["invoice_authorized"])
                self.assertIsNone(packet["collected_revenue"])

    def test_only_two_indicative_price_bands(self):
        self.assertEqual(set(q.NON_BINDING_RANGES),
                         {"website_diagnosis", "website_bounded_repair"})
        self.assertEqual(q.generate(sample())["indicative_non_binding_range"]["minimum"], 29)
        self.assertIsNone(q.generate(sample("farm_economics"))["indicative_non_binding_range"])

    def test_does_not_approve_any_offer_price(self):
        for code in q.PACKAGES:
            self.assertFalse(q.generate(sample(code))["price_approved"])

    def test_rejects_secondary_bot(self):
        with self.assertRaises(ValueError):
            q.generate(sample(canonical_bot="second.agent"))

    def test_rejects_credentials_and_pii(self):
        for field in ("email", "customer_name", "wallet", "password", "card"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                q.generate(sample(**{field: "DO_NOT_ECHO"}))

    def test_rejects_mismatched_package(self):
        with self.assertRaises(ValueError):
            q.generate(sample("farm_economics", work_package="single_fault_diagnosis"))

    def test_rejects_non_boolean_consent(self):
        with self.assertRaises(ValueError):
            q.generate(sample(consent=1))

    def test_missing_consent_preserves_blocker(self):
        packet = q.generate(sample(consent=False))
        self.assertIn("NO_CONTACT_CONSENT", packet["review_blockers"])

    def test_missing_stock_preserves_blocker(self):
        packet = q.generate(sample("cafe_b2b"))
        self.assertIn("STOCK_OR_CAPACITY_NOT_DOCUMENTED", packet["review_blockers"])

    def test_rights_gate_for_unreleased_digital_product(self):
        p = q.generate(sample("digital_publication", rights_documents=1,
                              delivery_documents=1))
        self.assertIn("PRODUCT_NOT_LIVE_OR_PROVEN", p["review_blockers"])

    def test_no_reported_sales_after_qualification(self):
        p = q.generate(sample("website_diagnosis"))
        self.assertFalse(p["quote_sent"])
        self.assertIsNone(p["collected_revenue"])

    def test_stdout_does_not_echo_untrusted_personal_data(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "input.json"
            path.write_text(json.dumps(sample(email="HIDDEN-CUSTOMER")))
            r = subprocess.run([sys.executable, str(ROOT / "scripts/revenue_cycle2_quote.py"),
                                str(path)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn("HIDDEN-CUSTOMER", r.stdout + r.stderr)

    def test_new_output_mode_0600(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = Path(t) / "input.json", Path(t) / "result.json"
            src.write_text(json.dumps(sample()))
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/revenue_cycle2_quote.py"),
                                   str(src), "--output", str(dst)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(stat.S_IMODE(dst.stat().st_mode), 0o600)
            self.assertFalse(json.loads(dst.read_text())["quote_sent"])

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as t:
            src, dst = Path(t) / "input.json", Path(t) / "result.json"
            src.write_text(json.dumps(sample()))
            dst.write_text("PRESERVE")
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/revenue_cycle2_quote.py"),
                                   str(src), "--output", str(dst)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(dst.read_text(), "PRESERVE")


if __name__ == "__main__":
    unittest.main()
