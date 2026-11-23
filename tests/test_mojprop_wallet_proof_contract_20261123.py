"""Contract tests only; trusted TronWeb v2 verification is NOT faked in production.

The mock signer is deliberately used only inside unit tests. There is no
customer payment, private key, real signature, mail or DB mutation here.
"""
import hashlib
from unittest.mock import Mock, patch

_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def synthetic_tron_address(marker: int) -> str:
    """Valid Base58Check structure for tests, not a funded live wallet."""
    payload = bytes([0x41]) + bytes([marker]) * 20
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(raw, "big")
    result = ""
    while n:
        n, remainder = divmod(n, 58)
        result = _BASE58[remainder] + result
    return result

from django.test import SimpleTestCase
from django.core import signing
from prop_firm.starter30_wallet_proof_contract import (
    WalletProofUnavailable,
    issue_wallet_proof_challenge,
    verify_wallet_proof,
)

SENDER = synthetic_tron_address(1)
RECIPIENT = synthetic_tron_address(2)
INVOICE = "MOJPROP30-EXACTINV12345678"
BUYER = "a" * 64
TERMS = "b" * 64
SIG = "0x" + "1" * 130


class Starter30WalletProofContractTests(SimpleTestCase):
    def issue(self, **kwargs):
        values = {
            "invoice_ref": INVOICE,
            "buyer_digest": BUYER,
            "sender": SENDER,
            "recipient": RECIPIENT,
            "terms_digest": TERMS,
        }
        values.update(kwargs)
        return issue_wallet_proof_challenge(**values)

    def verify(self, ticket, message, **kwargs):
        store = kwargs.pop("store", Mock(return_value=True))
        recover = kwargs.pop("recover", Mock(return_value=SENDER))
        values = {
            "ticket": ticket,
            "message": message,
            "signature": SIG,
            "expected_invoice": INVOICE,
            "expected_buyer_digest": BUYER,
            "expected_sender": SENDER,
            "expected_recipient": RECIPIENT,
            "expected_terms_digest": TERMS,
            "recover_signer": recover,
            "claim_nonce_once": store,
        }
        values.update(kwargs)
        return verify_wallet_proof(**values)

    def test_challenge_has_no_financial_action_and_precisely_bound_terms(self):
        ticket, message = self.issue()
        self.assertIn("Amount: 30000000 SUN (30 TRX)", message)
        self.assertIn("Purpose: Prove sending wallet control, not a transfer", message)
        self.assertIn(INVOICE, message)
        self.assertIn(SENDER, message)
        self.assertIn(RECIPIENT, message)
        self.assertIn("This signature does not send TRX", message)
        self.assertNotIn("private_key", message)
        payload = signing.loads(
            ticket, salt="mojprop-starter30-wallet-control-v1", max_age=600
        )
        self.assertEqual(payload["amount"], 30000000)
        self.assertEqual(payload["chain"], "tron-mainnet")
        self.assertEqual(len(payload["nonce"]), 64)

    def test_valid_signature_is_only_accepted_with_a_durable_replay_claim(self):
        ticket, message = self.issue()
        store = Mock(return_value=True)
        recover = Mock(return_value=SENDER)
        self.assertEqual(self.verify(ticket, message, store=store, recover=recover), SENDER)
        recover.assert_called_once_with(message, SIG)
        self.assertEqual(store.call_count, 1)
        args = store.call_args.args
        self.assertEqual(len(args[0]), 64)
        self.assertEqual(args[1], INVOICE)

    def test_no_verification_adapter_is_fail_closed(self):
        ticket, message = self.issue()
        for kw in ({"recover_signer": None}, {"claim_nonce_once": None}):
            with self.subTest(kw=kw):
                with self.assertRaisesRegex(WalletProofUnavailable, "unavailable"):
                    self.verify(ticket, message, **kw)

    def test_bad_or_wrong_signer_does_not_consume_nonce(self):
        ticket, message = self.issue()
        store = Mock(return_value=True)
        with self.assertRaisesRegex(WalletProofUnavailable, "does not match"):
            self.verify(ticket, message, store=store, recover=Mock(return_value=synthetic_tron_address(3)))
        store.assert_not_called()

    def test_altered_message_fails_before_recovering_signature(self):
        ticket, message = self.issue()
        recover = Mock(return_value=SENDER)
        with self.assertRaisesRegex(WalletProofUnavailable, "differs"):
            self.verify(ticket, message.replace("30000000", "30000001"), recover=recover)
        recover.assert_not_called()

    def test_cross_invoice_cross_buyer_cross_recipient_cross_contract_hold(self):
        ticket, message = self.issue()
        alterations = {
            "expected_invoice": "MOJPROP30-OTHER12345678",
            "expected_buyer_digest": "f" * 64,
            "expected_sender": "T" + "F" * 33,
            "expected_recipient": "T" + "G" * 33,
            "expected_terms_digest": "c" * 64,
        }
        for k, value in alterations.items():
            with self.subTest(field=k):
                with self.assertRaisesRegex(WalletProofUnavailable, "does not match"):
                    self.verify(ticket, message, **{k: value})

    def test_tampered_or_expired_ticket_rejected(self):
        ticket, message = self.issue()
        with self.assertRaisesRegex(WalletProofUnavailable, "invalid or expired"):
            self.verify(ticket + "X", message)
        with patch(
            "prop_firm.starter30_wallet_proof_contract.signing.loads",
            side_effect=signing.SignatureExpired("expired"),
        ):
            with self.assertRaisesRegex(WalletProofUnavailable, "invalid or expired"):
                self.verify(ticket, message)

    def test_double_use_is_rejected_by_durable_claim(self):
        ticket, message = self.issue()
        store = Mock(side_effect=[True, False])
        self.assertEqual(self.verify(ticket, message, store=store), SENDER)
        with self.assertRaisesRegex(WalletProofUnavailable, "already used"):
            self.verify(ticket, message, store=store)
        self.assertEqual(store.call_count, 2)

    def test_unavailable_nonce_database_does_not_grant_buyer_account(self):
        ticket, message = self.issue()
        with self.assertRaisesRegex(WalletProofUnavailable, "ledger unavailable"):
            self.verify(ticket, message, store=Mock(side_effect=OSError("down")))

    def test_bad_address_terms_or_invoice_rejected_before_ticket_issue(self):
        for changed in (
            {"sender": "invalid"},
            {"recipient": SENDER},
            {"invoice_ref": "short"},
            {"buyer_digest": "not-a-digest"},
            {"terms_digest": "X" * 64},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(WalletProofUnavailable):
                    self.issue(**changed)

    def test_untrusted_string_signature_or_noncanonical_encoding_rejected(self):
        ticket, message = self.issue()
        for raw in ("no", "0xABC", "0x" + "z" * 130):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(WalletProofUnavailable, "signature encoding"):
                    self.verify(ticket, message, signature=raw)

    def test_signed_challenge_is_unique_for_same_invoice(self):
        ticket_a, text_a = self.issue()
        ticket_b, text_b = self.issue()
        self.assertNotEqual(text_a, text_b)
        self.assertNotEqual(ticket_a, ticket_b)


if __name__ == "__main__":
    import unittest
    unittest.main()
