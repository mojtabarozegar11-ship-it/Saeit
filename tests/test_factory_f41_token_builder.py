"""Safety and deterministic output acceptance for isolated F41 token factory."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import factory_f41_token_builder as f41

HERE = Path(__file__).resolve().parents[1]
PILOT = HERE / "factory_config" / "f41_pilot_token.json"


class F41Tests(unittest.TestCase):
    def write_spec(self, folder, **updates):
        spec = json.loads(PILOT.read_text("utf8"))
        spec.update(updates)
        p = folder / "spec.json"
        p.write_text(json.dumps(spec), encoding="utf8")
        return p

    def test_valid_private_candidate_is_deterministic_and_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self.write_spec(root)
            receipt = f41.build(spec, root / "pilot")
            self.assertFalse(receipt["generation_100_verified"])
            self.assertFalse(receipt["quality_1000_certified"])
            self.assertFalse(receipt["commercial_release"])
            self.assertFalse(receipt["production_deployment_enabled"])
            self.assertEqual(receipt["transaction_broadcasts"], 0)
            self.assertEqual(receipt["site_writes"], 0)
            self.assertEqual(f41.verify(spec, root / "pilot"), receipt)
            source = (root / "pilot" / f41.FILES[0]).read_text()
            self.assertIn('import {TRC20}', source)
            self.assertIn("pragma solidity 0.8.20;", source)
            self.assertIn("_mint(msg.sender, 1000000000000000000000000)", source)
            self.assertNotIn("function mint(", source)
            obligations = json.loads((root / "pilot" / "quality-obligations.json").read_text())
            self.assertEqual(len(obligations["criteria"]), 100)
            self.assertTrue(all(c["approved_points"] == 0 for c in obligations["criteria"]))
            with self.assertRaisesRegex(ValueError, "F41_REQUIRES_NEW_DESTINATION"):
                f41.build(spec, root / "pilot")

    def test_100_billion_units_exact_not_issued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self.write_spec(root, name="Moj One Research", symbol="MOJ1",
                                   supply_tokens="100000000000")
            receipt = f41.build(spec, root / "candidate")
            self.assertEqual(receipt["total_supply_base_units"],
                             "100000000000000000000000000000")
            self.assertEqual(receipt["transaction_broadcasts"], 0)

    def test_wrong_network_and_source_injection_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for kwargs in (
                {"network": "mainnet"}, {"name": 'x"); mint(999); //'},
                {"symbol": "bad-name"}, {"supply_tokens": "1e40"},
                {"decimals": True}, {"supply_tokens": str(2 ** 256)},
                {"mode": "admin_mintable"}
            ):
                with self.subTest(kwargs=kwargs):
                    spec = self.write_spec(root, **kwargs)
                    with self.assertRaises(ValueError):
                        f41.build(spec, root / "candidate")
                    self.assertFalse((root / "candidate").exists())

    def test_tamper_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = self.write_spec(root)
            dest = root / "candidate"
            f41.build(spec, dest)
            (dest / f41.FILES[0]).write_text("corrupted")
            with self.assertRaisesRegex(ValueError, "TAMPERED"):
                f41.verify(spec, dest)
            link = root / "link"
            link.symlink_to(dest, target_is_directory=True)
            with self.assertRaises(ValueError):
                f41.verify(spec, link)

    def test_existing_40_family_contract_is_not_mutated(self):
        registry = json.loads((HERE / "factory_config" / "forty_families.json").read_text())
        self.assertEqual(len(registry["profiles"]), 40)
        self.assertNotIn("F41", {p["id"] for p in registry["profiles"]})


if __name__ == "__main__":
    unittest.main()
