"""Pure regression tests for the server-side merchant boundary."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from services.mpw_trx_merchant_binding import (
    MerchantBindingRejected,
    validate_tron_recipient,
    binding_for_request,
    validate_persisted_binding,
    require_same_invoice_host,
    require_current_merchant_for_invoice,
)


HOST = "mojplaywin.com"
RECEIVER = "TA4Wt1DUCqz6YegbnsmqsWC5uUfbdBqPxm"  # checksummed test-only fixture
SECOND_RECEIVER = "TA9pkx4DFxrEw8JZzUtyDrh2uAat1LDuJL"
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


    def test_base58check_accepts_two_valid_test_only_fixtures(self):
        self.assertEqual(validate_tron_recipient(RECEIVER), RECEIVER)
        self.assertEqual(validate_tron_recipient(SECOND_RECEIVER), SECOND_RECEIVER)

    def test_checksum_error_rejected_even_with_valid_t_prefix_and_length(self):
        corrupted = RECEIVER[:-1] + ("A" if RECEIVER[-1] != "A" else "B")
        self.assertEqual(len(corrupted), 34)
        with self.assertRaises(MerchantBindingRejected):
            validate_tron_recipient(corrupted)

    def test_empty_bogus_and_wrong_type_receivers_rejected(self):
        candidates = (
            None, False, True, 123, {}, [], b"TRON", "",
            "T" + "A" * 33, "T" + "B" * 33,
        )
        for candidate in candidates:
            with self.subTest(candidate=repr(candidate)), self.assertRaises(MerchantBindingRejected):
                validate_tron_recipient(candidate)

    def test_base58_alphabet_enforced(self):
        for symbol in ("0", "O", "I", "l", "!", "\\"):
            corrupted = RECEIVER[:5] + symbol + RECEIVER[6:]
            with self.subTest(symbol=symbol), self.assertRaises(MerchantBindingRejected):
                validate_tron_recipient(corrupted)

    def test_noncanonical_whitespace_and_length_rejected(self):
        for candidate in (
            " " + RECEIVER, RECEIVER + " ", RECEIVER + "\\n",
            RECEIVER[:-1], RECEIVER + "A", RECEIVER.lower(),
            RECEIVER[0:3] + "\\u200b" + RECEIVER[4:],
        ):
            with self.subTest(candidate=repr(candidate)), self.assertRaises(MerchantBindingRejected):
                validate_tron_recipient(candidate)

    def test_known_bad_network_prefix_rejected(self):
        # Valid Base58-looking non-TRON address cannot become a TRON receiver.
        for candidate in ("1BoatSLRHtKNngkdXEeobR76b53LETtpyT", "0" * 34):
            with self.subTest(candidate=candidate), self.assertRaises(MerchantBindingRejected):
                validate_tron_recipient(candidate)

    def test_registry_with_matching_but_checksum_invalid_receiver_rejected(self):
        bogus = "T" + "A" * 33
        config = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS={
            HOST: {**REGISTRY[HOST], "recipient": bogus},
        })
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(config, HOST, bogus)

    def test_registry_with_matching_blank_receiver_rejected(self):
        config = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS={
            HOST: {**REGISTRY[HOST], "recipient": ""},
        })
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(config, HOST, "")

    def test_other_valid_tron_receiver_cannot_reuse_merchants_registry(self):
        with self.assertRaises(MerchantBindingRejected):
            binding_for_request(self.settings, HOST, SECOND_RECEIVER)

    def test_invoice_with_corrupted_receiver_is_not_recoverable_as_valid(self):
        for recipient in (None, "", "T" + "A" * 33, RECEIVER + "A"):
            invoice = SimpleNamespace(
                network="tron-mainnet", recipient=recipient,
                merchant_domain=HOST, merchant_id="mojplaywin-store",
            )
            with self.subTest(recipient=recipient), self.assertRaises(MerchantBindingRejected):
                require_same_invoice_host(invoice, HOST)

    def test_valid_historical_invoice_remains_visible_after_registry_disabled(self):
        invoice = SimpleNamespace(
            network="tron-mainnet", recipient=RECEIVER,
            merchant_domain=HOST, merchant_id="mojplaywin-store",
        )
        disabled = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS={})
        self.assertEqual(require_same_invoice_host(invoice, HOST), HOST)
        with self.assertRaises(MerchantBindingRejected):
            require_current_merchant_for_invoice(disabled, HOST, invoice)


if __name__ == "__main__":
    unittest.main()
