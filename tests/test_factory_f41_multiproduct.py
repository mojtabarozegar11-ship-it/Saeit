"""Four independent F41 product families with real deterministic acceptance tests."""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory_f41_multi_product_builder as f41

ASSETS = ROOT / "factory_assets" / "f41_demo_assets"
SAMPLES = ROOT / "factory_config" / "f41_samples"


class MultiproductTests(unittest.TestCase):
    def request(self, kind):
        return SAMPLES / (kind + ".json")

    def test_all_four_produce_real_bytes_and_verified_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for kind in ("vesting", "reconciliation", "provenance", "nft_metadata"):
                with self.subTest(kind=kind):
                    out = base / kind
                    spec = self.request(kind)
                    receipt = f41.build(spec, out, ASSETS)
                    self.assertEqual(receipt["kind"], kind)
                    self.assertFalse(receipt["commercial_readiness"] == "READY")
                    self.assertFalse(receipt["quality_1000_certified"])
                    self.assertFalse(receipt["liquidity_guaranteed"])
                    self.assertEqual(receipt["transaction_broadcast_count"], 0)
                    self.assertEqual(f41.verify(spec, out, ASSETS), receipt)
                    self.assertGreaterEqual(len(receipt["file_sha256"]), 1)
                    with self.assertRaisesRegex(ValueError, "F41_OUTPUT_MUST_BE_NEW"):
                        f41.build(spec, out, ASSETS)

    def test_vesting_conserves_supply_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            f41.build(self.request("vesting"), base / "candidate")
            report = json.loads((base / "candidate" / "model.json").read_text())
            self.assertEqual(report["allocated"], "900000")
            self.assertEqual(report["unallocated"], "100000")
            self.assertEqual(report["sum_unlocked"], "900000")
            rows = list(csv.DictReader(io.StringIO((base / "candidate" / "vesting.csv").read_text())))
            self.assertEqual(sum(int(row["unlocked_base_units"]) for row in rows), 900000)

    def test_reconciliation_never_delivers_even_on_exact_match(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            f41.build(self.request("reconciliation"), base / "candidate")
            report = json.loads((base / "candidate" / "reconciliation.json").read_text())
            states = {x["invoice_id"]: x for x in report["records"]}
            self.assertTrue(states["order1"]["status"].startswith("MATCHED_INPUT_AWAITING"))
            self.assertEqual(states["order2"]["status"], "MISMATCH_MANUAL_REVIEW")
            self.assertFalse(report["chain_finality_independently_verified"])
            self.assertFalse(report["customer_delivery_enabled"])
            self.assertFalse(any(x["delivery_authorized"] for x in states.values()))

    def test_reconciliation_duplicate_txid_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = json.loads(self.request("reconciliation").read_text())
            spec["data"]["observations"].append(dict(spec["data"]["observations"][0]))
            request = root / "bad.json"
            request.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, "F41_DUPLICATE"):
                f41.build(request, root / "candidate")
            self.assertFalse((root / "candidate").exists())

    def test_provenance_and_nft_bind_actual_asset_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            media = base / "assets"
            media.mkdir()
            for name in ("demo_art.svg", "license_terms.txt"):
                (media / name).write_bytes((ASSETS / name).read_bytes())
            for kind in ("provenance", "nft_metadata"):
                target = base / kind
                f41.build(self.request(kind), target, media)
                self.assertEqual(f41.verify(self.request(kind), target, media)["kind"], kind)
            (media / "demo_art.svg").write_bytes(b"tampered")
            for kind in ("provenance", "nft_metadata"):
                with self.subTest(kind=kind):
                    with self.assertRaises(ValueError):
                        f41.verify(self.request(kind), base / kind, media)

    def test_mutated_quality_claim_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            dest = base / "candidate"
            f41.build(self.request("vesting"), dest)
            report = json.loads((dest / "manifest.json").read_text())
            report["quality_1000_certified"] = True
            (dest / "manifest.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "F41_MANIFEST_INTEGRITY_FAILED"):
                f41.verify(self.request("vesting"), dest)

    def test_catalog_does_not_claim_real_sales(self):
        catalog = json.loads((ROOT / "factory_config" / "f41_product_catalog.json").read_text())
        self.assertEqual(catalog["line_id"], "F41")
        self.assertEqual(len(catalog["active_builders"]), 5)
        self.assertFalse(catalog["cash_conversion_gate"]["commercial_sale_allowed"])
        self.assertEqual(catalog["cash_conversion_gate"]["verified_paying_customers"], 0)
        self.assertFalse(catalog["quality_1000_certified"])


if __name__ == "__main__":
    unittest.main()
