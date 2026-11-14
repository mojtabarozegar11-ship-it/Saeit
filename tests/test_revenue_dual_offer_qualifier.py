"""No-Django/no-network regression checks for the two revenue service offers."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "revenue_dual_offer_qualifier.py"
spec = importlib.util.spec_from_file_location("revenue_dual_offer_qualifier", ENGINE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RevenueOfferQualificationTests(unittest.TestCase):
    def entry(self, **changes):
        item = {
            "offer": "website_checkout_repair",
            "package": "diagnosis",
            "scope_items": 1,
            "evidence_items": 2,
            "consent_to_contact": True,
            "inputs_available": True,
            "synthetic_example": True,
        }
        item.update(changes)
        return item

    def test_diagnostic_band_is_nonbinding(self):
        got = module.qualify(self.entry())
        self.assertEqual(got["price_band_non_binding"], {
            "currency": "USD", "indicative_min": 29, "indicative_max": 49})
        self.assertEqual(got["qualification"], "manual_quote_review")
        self.assertEqual(got["order_state"], "inquiry_only")

    def test_repair_band_is_nonbinding(self):
        got = module.qualify(self.entry(package="bounded_repair"))
        self.assertEqual(got["price_band_non_binding"]["indicative_min"], 79)
        self.assertEqual(got["price_band_non_binding"]["indicative_max"], 149)

    def test_farm_has_no_invented_price(self):
        got = module.qualify(self.entry(offer="farm_break_even", package="analysis"))
        self.assertIsNone(got["price_band_non_binding"])
        self.assertIn("local_price_not_approved", got["blockers"])

    def test_rejects_unrecognized_offer(self):
        with self.assertRaises(ValueError):
            module.qualify(self.entry(offer="fake"))

    def test_rejects_cross_offer_package(self):
        with self.assertRaises(ValueError):
            module.qualify(self.entry(offer="farm_break_even", package="diagnosis"))

    def test_missing_contact_consent_blocks(self):
        got = module.qualify(self.entry(consent_to_contact=False))
        self.assertIn("contact_consent_missing", got["blockers"])

    def test_missing_inputs_blocks(self):
        got = module.qualify(self.entry(inputs_available=False))
        self.assertIn("minimum_inputs_missing", got["blockers"])

    def test_zero_evidence_blocks(self):
        got = module.qualify(self.entry(evidence_items=0))
        self.assertIn("no_supporting_evidence", got["blockers"])

    def test_unbounded_scope_blocks(self):
        got = module.qualify(self.entry(scope_items=4))
        self.assertIn("scope_exceeds_bounded_offer", got["blockers"])

    def test_rejects_negative_or_boolean_counts(self):
        for value in (-1, True, 0, 21, 1.3, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.qualify(self.entry(scope_items=value))

    def test_rejects_extra_personal_fields(self):
        with self.assertRaisesRegex(ValueError, "PII"):
            module.qualify(self.entry(email="someone@example.invalid"))

    def test_rejects_non_boolean_consent(self):
        with self.assertRaises(ValueError):
            module.qualify(self.entry(consent_to_contact="yes"))

    def test_no_economic_side_effects(self):
        for offer, package in (("website_checkout_repair", "diagnosis"),
                               ("website_checkout_repair", "bounded_repair"),
                               ("farm_break_even", "analysis")):
            got = module.qualify(self.entry(offer=offer, package=package))
            self.assertEqual(got["canonical_bot"], "mojtaba.bot.ai")
            self.assertEqual(got["payment_state"], "not_requested")
            self.assertEqual(got["delivery_state"], "not_delivered")
            self.assertFalse(got["auto_send_enabled"])
            self.assertFalse(got["personal_data_exported"])
            self.assertNotIn("customer_email", got)

    def test_rejects_non_object_input(self):
        for value in (None, [], "x", 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.qualify(value)

    def test_cli_end_to_end_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "intake.json"
            out = Path(tmp) / "redacted.json"
            src.write_text(json.dumps(self.entry()), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(src),
                                   "--output", str(out)],
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["qualification"], "manual_quote_review")
            self.assertEqual(saved["order_state"], "inquiry_only")

    def test_cli_rejects_output_over_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "intake.json"
            src.write_text(json.dumps(self.entry()), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(src),
                                   "--output", str(src)],
                                  capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refusing to overwrite", proc.stderr)


    def test_cli_rejects_symlinked_customer_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "intake.json"
            source.write_text(json.dumps(self.entry()), encoding="utf-8")
            link = Path(tmp) / "alias.json"
            link.symlink_to(source)
            proc = subprocess.run([sys.executable, str(ENGINE), str(link)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("intake symlink rejected", proc.stderr)

    def test_cli_duplicate_consent_cannot_overwrite_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "intake.json"
            data = json.dumps(self.entry()).replace(
                '"consent_to_contact": true',
                '"consent_to_contact": false, "consent_to_contact": true',
            )
            source.write_text(data, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(source)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("ambiguous JSON intake", proc.stderr)

    def test_cli_nonfinite_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "intake.json"
            data = json.dumps(self.entry()).replace('"evidence_items": 2',
                                                    '"evidence_items": NaN')
            source.write_text(data, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(source)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("ambiguous JSON intake", proc.stderr)

    def test_cli_does_not_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, output = Path(tmp) / "in.json", Path(tmp) / "existing.json"
            src.write_text(json.dumps(self.entry()), encoding="utf-8")
            output.write_text("ORIGINAL", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(src),
                                   "--output", str(output)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("refusing to overwrite", proc.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "ORIGINAL")

    def test_cli_output_keeps_only_anonymized_bot_triage(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, output = Path(tmp) / "in.json", Path(tmp) / "new.json"
            src.write_text(json.dumps(self.entry()), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(src),
                                   "--output", str(output)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(saved["canonical_bot"], "mojtaba.bot.ai")
            self.assertEqual(saved["order_state"], "inquiry_only")
            self.assertEqual(saved["payment_state"], "not_requested")
            self.assertNotIn("personal_email", saved)
            self.assertFalse(saved["auto_send_enabled"])

    def test_cli_output_access_is_private(self):
        import os
        import stat
        with tempfile.TemporaryDirectory() as tmp:
            src, output = Path(tmp) / "in.json", Path(tmp) / "new.json"
            src.write_text(json.dumps(self.entry()), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ENGINE), str(src),
                                   "--output", str(output)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(output.stat().st_mode) & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
