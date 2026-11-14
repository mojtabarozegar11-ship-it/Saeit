"""Offline proof that a source catalogue and synthetic KPIs do not invent sales."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mojtaba_revenue_portfolio.py"
spec = importlib.util.spec_from_file_location("mojtaba_revenue_portfolio", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic(**overrides):
    data = {"schema": "mojtaba.bot.ai.synthetic-funnel.v1", "synthetic_example": True,
            "counts": {"views": 100, "inquiries": 10, "qualified": 5,
                       "approved_quotes": 4, "settled_orders": 2,
                       "delivered_orders": 1}}
    data.update(overrides)
    return data


class RevenuePortfolioTests(unittest.TestCase):
    def test_only_one_canonical_bot(self):
        cat = module.catalogue()
        self.assertEqual(cat["canonical_bot"], "mojtaba.bot.ai")
        self.assertTrue(all(x["canonical_bot"] == "mojtaba.bot.ai" for x in cat["items"]))

    def test_all_models_are_blocked_not_live(self):
        self.assertTrue(all(x["commercial_release"] == "blocked_unverified"
                            for x in module.catalogue()["items"]))

    def test_existing_site_drafts_are_only_two(self):
        c = module.catalogue()
        self.assertEqual(c["existing_draft_inquiry_count"], 2)
        self.assertEqual({x["code"] for x in c["items"] if x["source_status"] == "draft_inquiry_source"},
                         {"website_checkout_repair", "farm_break_even"})

    def test_all_candidates_use_only_existing_two_sites(self):
        self.assertEqual({i["site"] for i in module.catalogue()["items"]},
                         {"mojplaywin.com", "zomorodmelal.ir"})

    def test_each_model_has_all_eight_missing_release_gates(self):
        self.assertTrue(all(len(x["missing_verified_gates"]) == 8
                            for x in module.catalogue()["items"]))

    def test_all_revenue_money_fields_are_unknown(self):
        c = module.catalogue()
        self.assertIsNone(c["collected_revenue"])
        self.assertIsNone(c["commercially_verified_count"])
        self.assertTrue(all(i["revenue_collected"] is None for i in c["items"]))

    def test_no_automated_sale_contact_or_payment(self):
        for i in module.catalogue()["items"]:
            self.assertFalse(i["autonomous_payment"])
            self.assertFalse(i["auto_contact"])

    def test_model_count_and_unique_codes(self):
        c = module.catalogue()
        codes = [i["code"] for i in c["items"]]
        self.assertEqual(len(codes), 11)
        self.assertEqual(len(set(codes)), 11)

    def test_percentages_on_same_synthetic_cohort(self):
        r = module.funnel(synthetic())
        self.assertEqual(r["ratios_percent"], {
            "inquiry": "10.00", "qualification": "50.00", "quote": "80.00",
            "settled_order_per_quote": "50.00", "delivery_per_settled_order": "50.00"})

    def test_none_on_zero_denominator(self):
        r = module.funnel(synthetic(counts=dict.fromkeys(module.FUNNEL_KEYS, 0)))
        self.assertTrue(all(v is None for v in r["ratios_percent"].values()))

    def test_no_real_revenue_in_synthetic_results(self):
        r = module.funnel(synthetic())
        self.assertIsNone(r["real_revenue"])
        self.assertIsNone(r["real_conversion_rates"])
        self.assertFalse(r["automated_sales_enabled"])

    def test_real_customer_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            module.funnel(synthetic(synthetic_example=False))

    def test_missing_or_extra_fields_are_rejected(self):
        for x in (None, [], {}, synthetic(email="address@example.invalid")):
            with self.subTest(x=x), self.assertRaises(ValueError):
                module.funnel(x)

    def test_customer_identifiers_in_counts_rejected(self):
        x = synthetic();x["counts"]["customer_email"] = "secret@example.invalid"
        with self.assertRaises(ValueError):
            module.funnel(x)

    def test_float_negative_boolean_and_huge_counts_rejected(self):
        for value in (True, -1, 1.5, 1_000_000_001, "10", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                x = synthetic(); x["counts"]["inquiries"] = value
                module.funnel(x)

    def test_nonmonotone_cohort_rejected(self):
        x = synthetic();x["counts"]["qualified"] = 99
        with self.assertRaisesRegex(ValueError, "monotone"):
            module.funnel(x)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            json.loads('{"x":1,"x":2}', object_pairs_hook=module._unique_pairs)

    def test_cli_catalogue_no_private_data(self):
        p = subprocess.run([sys.executable, str(SCRIPT), "--catalogue"],
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout)
        self.assertEqual(out["canonical_bot"], "mojtaba.bot.ai")
        self.assertIsNone(out["collected_revenue"])

    def test_cli_synthetic_funnel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cohort.json"
            path.write_text(json.dumps(synthetic()), encoding="utf-8")
            p = subprocess.run([sys.executable, str(SCRIPT), "--synthetic-funnel", str(path)],
                               text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue(json.loads(p.stdout)["synthetic_example"])

    def test_cli_rejects_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nan.json"
            path.write_text('{"schema":"x","synthetic_example":true,"counts":NaN}')
            p = subprocess.run([sys.executable, str(SCRIPT), "--synthetic-funnel", str(path)],
                               text=True, capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("nonfinite JSON", p.stderr)

    def test_cli_rejects_symlink_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.json"
            path.write_text(json.dumps(synthetic()))
            link = Path(tmp) / "link.json"
            link.symlink_to(path)
            p = subprocess.run([sys.executable, str(SCRIPT), "--synthetic-funnel", str(link)],
                               text=True, capture_output=True)
            self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__": unittest.main()
