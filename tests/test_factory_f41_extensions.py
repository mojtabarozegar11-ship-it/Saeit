"""F41 15 executable offline extension families: deterministic output and fail-closed receipt."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory_f41_multi_product_builder as f41

SAMPLES = ROOT / "factory_config" / "f41_samples"
ASSETS = ROOT / "factory_assets" / "f41_demo_assets"

class ExtensionTests(unittest.TestCase):
    def test_all_15_real_offline_candidates(self):
        cases = tuple(f41.TYPES)[4:]
        self.assertEqual(len(cases), 15)
        with tempfile.TemporaryDirectory() as tmp:
            for kind in cases:
                with self.subTest(kind=kind):
                    req = SAMPLES / (kind + ".json")
                    dest = Path(tmp) / kind
                    receipt = f41.build(req, dest, ASSETS)
                    self.assertEqual(receipt["kind"], kind)
                    self.assertEqual(receipt["transaction_broadcast_count"], 0)
                    self.assertFalse(receipt["quality_1000_certified"])
                    self.assertEqual(receipt, f41.verify(req, dest, ASSETS))
                    self.assertTrue(receipt["file_sha256"])
                    target = next(p for p in dest.iterdir() if p.name != "manifest.json")
                    target.write_bytes(b"corrupted")
                    with self.assertRaises(ValueError):
                        f41.verify(req, dest, ASSETS)

    def test_royalties_conserve_every_base_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/"royalty"
            f41.build(SAMPLES/"royalty_accounting.json",out,ASSETS)
            control=json.loads((out/"royalty-control.json").read_text())
            self.assertEqual(control["total_net"],control["royalty_allocated"])
            self.assertEqual(control["transfers_executed"],0)

    def test_watch_sdk_validates_checksum_and_never_signs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"wallet"
            f41.build(SAMPLES/"watch_wallet_sdk.json",out,ASSETS)
            sys.path.insert(0,str(out))
            try:
                import watch_wallet
                self.assertTrue(watch_wallet.verify_tron_address("TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNQ"))
                self.assertFalse(watch_wallet.verify_tron_address("TWTBsKZPVuQgaGNbyJWJm9XR28g4wVBCNR"))
            finally:
                sys.path.remove(str(out))

    def test_produced_fuzzer_runs_real_property_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"fuzz"
            f41.build(SAMPLES/"contract_fuzz.json",out,ASSETS)
            check=subprocess.run([sys.executable,str(out/"fuzz_vesting.py")],
                capture_output=True,text=True,timeout=10,check=True)
            self.assertIn("F41_OFFLINE_PROPERTY_CHECKS=1000",check.stdout)

    def test_duplicate_bridge_message_or_bad_royalty_split_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for kind in ("bridge_risk","royalty_accounting"):
                data=json.loads((SAMPLES/(kind+".json")).read_text())
                if kind=="bridge_risk":
                    data["data"]["messages"].append(dict(data["data"]["messages"][0]))
                else:
                    data["data"]["payees"][0]["basis_points"]=6000
                request=root/(kind+".json")
                request.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    f41.build(request,root/(kind+"-output"),ASSETS)
                self.assertFalse((root/(kind+"-output")).exists())
if __name__=="__main__":
    unittest.main()
