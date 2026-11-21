"""Offline validation for 12 brands x 2 proposed coins. No network required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import brand_24_coin_specs as registry
from scripts import factory_f41_token_builder_v2 as f41


class Brand24CoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = registry.read_registry()

    def test_twelve_brands_two_coins_distinct(self):
        specs = registry.validate_registry(self.data)
        self.assertEqual(len(specs), 24)
        self.assertEqual(len({t["symbol"] for b in self.data["brands"] for t in b["tokens"]}), 24)
        self.assertEqual({b["brand_slug"] for b in self.data["brands"]}, set(registry.EXPECTED_BRANDS))

    def test_every_generated_spec_accepted_by_existing_f41_builder(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "source-specs"
            self.assertEqual(registry.write_specs(self.data, target), 24)
            self.assertEqual(registry.verify_specs(self.data, target), 24)
            for file in target.glob("*.json"):
                obj, units = f41.spec_read(file)
                self.assertEqual(obj["network"], "shasta")
                self.assertEqual(units, int(obj["supply_tokens"]) * (10 ** 18))

    def test_reject_duplicate_symbol(self):
        altered = copy.deepcopy(self.data)
        altered["brands"][1]["tokens"][0]["symbol"] = altered["brands"][0]["tokens"][0]["symbol"]
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TOKEN_IDENTITY"):
            registry.validate_registry(altered)

    def test_reject_mainnet_and_broadcast_flags(self):
        altered = copy.deepcopy(self.data)
        altered["mainnet_network"] = "tron-mainnet"
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_CHAIN_OR_STAGE"):
            registry.validate_registry(altered)
        altered = copy.deepcopy(self.data)
        altered["deployment"]["testnet_broadcast_enabled"] = True
        with self.assertRaisesRegex(ValueError, "DEPLOYMENT_AND_PAYMENT_MUST_REMAIN_DISABLED"):
            registry.validate_registry(altered)

    def test_reject_fictitious_address_and_sale(self):
        altered = copy.deepcopy(self.data)
        altered["brands"][0]["tokens"][0]["contract_address"] = "unverified"
        with self.assertRaisesRegex(ValueError, "NON_OFFLINE_OR_UNAPPROVED_TOKEN"):
            registry.validate_registry(altered)
        altered = copy.deepcopy(self.data)
        altered["deployment"]["public_sale_enabled"] = True
        with self.assertRaisesRegex(ValueError, "DEPLOYMENT_AND_PAYMENT_MUST_REMAIN_DISABLED"):
            registry.validate_registry(altered)

    def test_no_overwrite_and_detect_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "specs"
            registry.write_specs(self.data, target)
            with self.assertRaisesRegex(ValueError, "OUTPUT_DESTINATION_MUST_BE_NEW"):
                registry.write_specs(self.data, target)
            one = next(target.glob("*.json"))
            one.write_text("{}\n", "utf-8")
            with self.assertRaisesRegex(ValueError, "OUTPUT_SPEC_MISMATCH"):
                registry.verify_specs(self.data, target)


if __name__ == "__main__":
    unittest.main()
