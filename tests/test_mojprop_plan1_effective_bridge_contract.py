from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EffectivePlan1BridgeContractTests(unittest.TestCase):
    def test_contract_is_exact_native_trx_and_fail_closed(self):
        source = (ROOT / "prop_firm" / "plan1_invoice.py").read_text()
        self.assertIn('PRODUCT_CODE = "MOJ-PROP-01"', source)
        self.assertIn('CONTRACT_VERSION = "2026-11-15/v1.2"', source)
        self.assertIn("AMOUNT_SUN = 30_000_000", source)
        self.assertIn('NETWORK = "tron-mainnet"', source)
        self.assertIn("missing = [name for name in REQUIRED_GATES", source)

    def test_public_view_has_no_reconcile_or_transfer_operation(self):
        source = (ROOT / "prop_firm" / "plan1_views.py").read_text()
        self.assertIn("HttpResponseNotFound", source)
        self.assertNotIn("record_verified_settlement", source)
        self.assertNotIn("requests.", source)
        self.assertNotIn("send", source.lower())

    def test_route_is_runtime_guarded(self):
        source = (ROOT / "config" / "urls.py").read_text()
        self.assertIn("MPW_MOJPROP_PLAN1_ROUTE_ENABLED", source)
        self.assertIn("prop_firm.plan1_urls", source)

    def test_persistence_has_global_txid_guard(self):
        source = (ROOT / "prop_firm" / "plan1_persistence.py").read_text()
        self.assertIn("TronSettlementLedger.objects.create", source)
        self.assertIn("except IntegrityError", source)
        self.assertIn("trusted_reconciler_attestation is not True", source)


if __name__ == "__main__":
    unittest.main()
