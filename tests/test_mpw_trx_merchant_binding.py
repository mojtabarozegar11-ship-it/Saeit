"""Pure regression tests for the server-side merchant boundary."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from services.mpw_trx_merchant_binding import (
    MerchantBindingRejected,
    binding_for_request,
    validate_persisted_binding,
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


if __name__ == "__main__":
    unittest.main()
