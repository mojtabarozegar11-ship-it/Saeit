"""Wallet extracted from owner-submitted native TRON Receive QR (not OCR).

Tests only checksum, host, merchant identity and disabled-by-default invoice
policy. No private key, chain RPC, customer funds, fake receipt or live write.
"""
import unittest
from types import SimpleNamespace

from services.mpw_trx_merchant_binding import (
    MerchantBindingRejected,
    validate_tron_recipient,
)
from services.mojtaba_tron_owner_receiver import (
    APPROVED_NATIVE_TRX_RECIPIENT,
    MAINNET, ASSET, DECIMALS, MERCHANT_DOMAIN, MERCHANT_ID,
    approved_recipient, owner_merchant_registry,
    require_owner_trx_binding, public_receiving_terms,
)


class QRVerifiedOwnerReceiverTests(unittest.TestCase):
    def test_owner_qr_payload_and_base58_checksum(self):
        self.assertEqual(
            APPROVED_NATIVE_TRX_RECIPIENT,
            "THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73",
        )
        self.assertEqual(len(approved_recipient()), 34)
        self.assertEqual(validate_tron_recipient(APPROVED_NATIVE_TRX_RECIPIENT),
                         APPROVED_NATIVE_TRX_RECIPIENT)

    def test_lookalike_z_is_not_the_qr_address_and_has_bad_checksum(self):
        visually_ambiguous = APPROVED_NATIVE_TRX_RECIPIENT.replace("Uksd2Un", "UksdZUn")
        self.assertNotEqual(visually_ambiguous, APPROVED_NATIVE_TRX_RECIPIENT)
        with self.assertRaises(MerchantBindingRejected):
            validate_tron_recipient(visually_ambiguous)
        with self.assertRaises(MerchantBindingRejected):
            owner_merchant_registry(recipient=visually_ambiguous)

    def test_safe_default_registry_not_payable(self):
        registry = owner_merchant_registry()
        self.assertEqual(set(registry), {MERCHANT_DOMAIN})
        self.assertFalse(registry[MERCHANT_DOMAIN]["enabled"])
        self.assertEqual(registry[MERCHANT_DOMAIN]["recipient"], approved_recipient())
        with self.assertRaises(MerchantBindingRejected):
            require_owner_trx_binding(
                SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry),
                MERCHANT_DOMAIN,
            )

    def test_both_independent_releases_are_required(self):
        for invoice, finality in ((False, False), (False, True), (True, False)):
            with self.subTest(invoice=invoice, finality=finality):
                registry = owner_merchant_registry(
                    invoice_enabled=invoice, finality_enabled=finality,
                )
                self.assertFalse(registry[MERCHANT_DOMAIN]["enabled"])
                with self.assertRaises(MerchantBindingRejected):
                    require_owner_trx_binding(
                        SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry),
                        MERCHANT_DOMAIN,
                    )

    def test_exact_host_binding_with_both_verifications(self):
        registry = owner_merchant_registry(
            invoice_enabled=True, finality_enabled=True,
        )
        binding = require_owner_trx_binding(
            SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry),
            MERCHANT_DOMAIN,
        )
        self.assertEqual(binding.domain, MERCHANT_DOMAIN)
        self.assertEqual(binding.merchant_id, MERCHANT_ID)
        self.assertEqual(binding.recipient, APPROVED_NATIVE_TRX_RECIPIENT)
        self.assertEqual(binding.network, MAINNET)

    def test_no_implicit_www_or_company_alias(self):
        registry = owner_merchant_registry(
            invoice_enabled=True, finality_enabled=True,
        )
        settings = SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry)
        for host in ("www.mojplaywin.com", "zomorodmelal.ir",
                     "mojtaba.bot.ai", "evil.mojplaywin.com"):
            with self.subTest(host=host), self.assertRaises(MerchantBindingRejected):
                require_owner_trx_binding(settings, host)

    def test_boolean_identity_strict_not_truthy_strings(self):
        for kwargs in (
            {"invoice_enabled": 1, "finality_enabled": True},
            {"invoice_enabled": True, "finality_enabled": "true"},
            {"invoice_enabled": None, "finality_enabled": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(MerchantBindingRejected):
                owner_merchant_registry(**kwargs)

    def test_merchant_registry_and_public_terms_are_immutable(self):
        registry = owner_merchant_registry()
        with self.assertRaises(TypeError):
            registry["www.mojplaywin.com"] = registry[MERCHANT_DOMAIN]
        with self.assertRaises(TypeError):
            registry[MERCHANT_DOMAIN]["recipient"] = "wrong"
        public = public_receiving_terms()
        self.assertEqual(public["asset"], "TRX")
        self.assertEqual(public["network"], "tron-mainnet")
        self.assertEqual(public["decimals"], 6)
        self.assertEqual(public["recipient"], APPROVED_NATIVE_TRX_RECIPIENT)
        self.assertIsNone(public["amount_sun"])
        self.assertIsNone(public["invoice_id"])
        self.assertIs(public["payment_verified"], False)
        self.assertIs(public["paid_entitlement"], False)
        self.assertIs(public["checkout_live"], False)

    def test_sender_for_historical_canary_is_not_auto_registered_as_receiver(self):
        registry = owner_merchant_registry(invoice_enabled=True, finality_enabled=True)
        with self.assertRaises(MerchantBindingRejected):
            from services.mpw_trx_merchant_binding import binding_for_request
            binding_for_request(
                SimpleNamespace(MPW_TRX_MERCHANT_BINDINGS=registry),
                MERCHANT_DOMAIN, "TA4Wt1DUCqz6YegbnsmqsWC5uUfbdBqPxm",
            )


if __name__ == "__main__":
    unittest.main()
