"""Pure regression tests for the server-side merchant boundary."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from services.mpw_trx_merchant_binding import (
    MerchantBindingRejected,
    binding_for_request,
    validate_persisted_binding,
    require_same_invoice_host,
    require_current_merchant_for_invoice,
)


HOST = "mojplaywin.com"
RECEIVER = "T" + "A" * 33
REGISTRY = {
    HOST: {
        "domain": HOST,
        "merchant_id": "mojplaywin-store",
        "network": "tron-mainnet",
        "recipient": RECEIVER,
        "enabled": True,
    },
}


class MerchantBindingTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=REGISTRY)

    def test_exact_registered_host_and_receiver_resolve(self):
        binding = binding_for_request(self.settings, HOST, RECEIVER)
        self.assertEqual(binding.domain, HOST)
        self.assertEqual(binding.merchant_id, "mojplaywin-store")
        self.assertEqual(binding.network, "tron-mainnet")

    def test_unregistered_www_alias_is_not_implicitly_accepted(self):
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(self.settings, "www." + HOST, RECEIVER)

    def test_receiver_cannot_be_reassigned_to_another_host(self):
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(self.settings, HOST, "T" + "B" * 33)

    def test_disabled_registry_entry_fails_closed(self):
        disabled = {HOST: {**REGISTRY[HOST], "enabled": False}}
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(
                SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=disabled),
                HOST,
                RECEIVER,
            )

    def test_persisted_identity_is_canonical(self):
        self.assertEqual(
            validate_persisted_binding("MojPlayWin.COM.", "MojPlayWin-Store"),
            (HOST, "mojplaywin-store"),
        )

    def test_persisted_identity_rejects_path_or_bad_id(self):
        with self.assertRaises(MerchantBindingRejected):
            validate_persisted_binding("https://"+HOST, "mojplaywin-store")
        with self.assertRaises(MerchantBindingRejected):
            validate_persisted_binding(HOST, "bad id")


    def test_only_merchant_that_issued_invoice_may_display_it(self):
        intent = SimpleNamespace(
            network="tron-mainnet", recipient=RECEIVER,
            merchant_domain=HOST, merchant_id="mojplaywin-store",
        )
        self.assertEqual(require_same_invoice_host(intent, HOST), HOST)
        with self.assertRaises(MerchantBindingRejected):
            require_same_invoice_host(intent, "www." + HOST)
        with self.assertRaises(MerchantBindingRejected):
            require_same_invoice_host(intent, "another-merchant.com")

    def test_disable_registry_does_not_destroy_owner_of_historical_receipt(self):
        intent = SimpleNamespace(
            network="tron-mainnet", recipient=RECEIVER,
            merchant_domain=HOST, merchant_id="mojplaywin-store",
        )
        disabled = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS={
            HOST: {**REGISTRY[HOST], "enabled": False},
        })
        self.assertEqual(require_same_invoice_host(intent, HOST), HOST)
        with self.assertRaises(MerchantBindingRejected):
            require_current_merchant_for_invoice(disabled, HOST, intent)

    def test_pending_invoice_reuse_requires_current_merchant_id(self):
        invoice = SimpleNamespace(
            network="tron-mainnet", recipient=RECEIVER,
            merchant_domain=HOST, merchant_id="mojplaywin-store",
        )
        self.assertEqual(
            require_current_merchant_for_invoice(self.settings, HOST, invoice).merchant_id,
            "mojplaywin-store",
        )
        drifted = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS={
            HOST: {**REGISTRY[HOST], "merchant_id": "other-merchant"},
        })
        with self.assertRaises(MerchantBindingRejected):
            require_current_merchant_for_invoice(drifted, HOST, invoice)

    def test_host_alias_cannot_masquerade_as_same_merchant_id(self):
        alias = "www." + HOST
        registry = {**REGISTRY, alias: {
            **REGISTRY[HOST], "domain": alias,
        }}
        invoice = SimpleNamespace(
            network="tron-mainnet", recipient=RECEIVER,
            merchant_domain=HOST, merchant_id="mojplaywin-store",
        )
        with self.assertRaises(MerchantBindingRejected):
            require_current_merchant_for_invoice(
                SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry),
                alias, invoice,
            )

    def test_bad_persisted_identity_and_wrong_network_deny_reuse(self):
        for changes in (
            {"merchant_domain": None},
            {"merchant_id": None},
            {"merchant_id": []},
            {"merchant_domain": "https://mojplaywin.com"},
            {"network": "tron-testnet"},
            {"recipient": None},
        ):
            original = {
                "network": "tron-mainnet", "recipient": RECEIVER,
                "merchant_domain": HOST, "merchant_id": "mojplaywin-store",
            }
            with self.subTest(changes=changes), self.assertRaises(MerchantBindingRejected):
                require_same_invoice_host(SimpleNamespace(**(original | changes)), HOST)


if __name__ == "__main__":
    unittest.main()
