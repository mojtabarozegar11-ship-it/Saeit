"""Offline TRON address checksum, independent-domain and owner gate tests.

All wallet addresses are synthetically generated, not funded or controlled.
"""
import hashlib
import unittest

from scripts.mpw_tron_domain_receiver_gate_20261115 import (
    ALPHABET, REQUIRED_DOCUMENTATION, assess_receiver_manifest,
    domain_valid, tron_base58check_valid,
)


def synthetic_tron_address(tag, prefix=0x41):
    payload = bytes([prefix]) + bytes([tag]) * 20
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n = int.from_bytes(payload + checksum, "big")
    out = ""
    while n:
        n, k = divmod(n, 58)
        out = ALPHABET[k] + out
    return out


def record(domain="mojplaywin.com", tag=7):
    entry = {
        "domain": domain, "receiver": synthetic_tron_address(tag),
        "live_payments_enabled": False,
    }
    entry.update({field: "external-review-reference-not-proof"
                  for field in REQUIRED_DOCUMENTATION})
    return entry


class TronDomainReceiverSafetyTests(unittest.TestCase):
    def test_valid_synthetic_mainnet_checksum_not_sufficient_for_money(self):
        r = record()
        self.assertTrue(tron_base58check_valid(r["receiver"]))
        result = assess_receiver_manifest([r])
        self.assertEqual(result["gate"], "candidate_for_independent_owner_review")
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["real_money_enabled"])
        self.assertNotIn(r["receiver"], str(result))

    def test_invalid_checksum_prefix_and_non_string_wallet(self):
        addr = synthetic_tron_address(8)
        for invalid in (
            addr[:-1] + ("1" if addr[-1] != "1" else "2"),
            synthetic_tron_address(8, prefix=0x42),
            "T" * 34, "0x41" + "a" * 40, None, 123, {}, [],
        ):
            with self.subTest(invalid=str(invalid)[:10]):
                self.assertFalse(tron_base58check_valid(invalid))

    def test_domain_syntax_never_accepts_url_or_lookalike_structure(self):
        for domain in (
            "", ".", "mojplaywin", "https://mojplaywin.com",
            "MojPlayWin.com", "mojplaywin.com:443", "*.mojplaywin.com",
            "-fake.mojplaywin.com", "foo..mojplaywin.com", "a" * 64 + ".com",
            None, 123, ["mojplaywin.com"],
        ):
            with self.subTest(domain=str(domain)[:35]):
                self.assertFalse(domain_valid(domain))
        self.assertTrue(domain_valid("mojtaba.bot.ai"))
        self.assertTrue(domain_valid("store.mojplaywin.com"))
        self.assertTrue(domain_valid("zomorodmelal.ir"))

    def test_duplicate_domain_or_shared_wallet_is_not_independent(self):
        both = [record("mojplaywin.com", 7), record("store.mojplaywin.com", 7)]
        x = assess_receiver_manifest(both)
        self.assertIn("row_1_shared_wallet_not_independently_settled", x["errors"])
        self.assertFalse(x["release_authorized"])
        y = assess_receiver_manifest([record(), record()])
        self.assertIn("row_1_duplicate_domain", y["errors"])

    def test_missing_each_evidence_or_live_activation_is_blocked(self):
        for key in REQUIRED_DOCUMENTATION:
            r = record()
            r[key] = ""
            with self.subTest(missing=key):
                x = assess_receiver_manifest([r])
                self.assertIn("row_0_missing_" + key, x["errors"])
                self.assertEqual(x["gate"], "blocked")
        for flag in (None, True, 1, "false"):
            r = record()
            r["live_payments_enabled"] = flag
            with self.subTest(flag=flag):
                x = assess_receiver_manifest([r])
                self.assertIn("row_0_live_payment_must_remain_disabled", x["errors"])

    def test_no_receiver_or_wrong_input_denied_without_wallet_leak(self):
        self.assertIn("no_domain_receivers", assess_receiver_manifest([])["errors"])
        for invalid in ({}, None, "[]", False):
            self.assertEqual(assess_receiver_manifest(invalid)["gate"], "blocked")
        x = assess_receiver_manifest([None, record()])
        self.assertIn("row_0_invalid", x["errors"])
        self.assertFalse(x["release_authorized"])


if __name__ == "__main__":
    unittest.main()
