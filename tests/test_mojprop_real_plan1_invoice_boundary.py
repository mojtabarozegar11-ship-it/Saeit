"""Offline negative tests for REAL Plan1 invoice boundary; no payment side effects."""
import unittest
from dataclasses import replace
from services.mojprop_real_plan1_invoice_boundary import (
    Enrollment, TrustedFact, REQUIRED_PROOFS, authorize_candidate,
    InvoiceBoundaryRejected,
)
NOW = 1_800_000_000
DIGEST = "a" * 64
ORDER = "MOJPROP01-ABCDEFGHIJKL"

def valid():
    enrollment = Enrollment(ORDER, "buyer-1", "MOJ-PROP-01",
                            "2026-11-15/v1.2", DIGEST, "tron-mainnet",
                            30_000_000, "approved")
    sources = {name: "trusted:" + name for name in REQUIRED_PROOFS}
    facts = {name: TrustedFact(sources[name], ORDER, True, DIGEST,
                               NOW - 10, NOW + 10) for name in REQUIRED_PROOFS}
    return enrollment, facts, sources

class InvoiceBoundaryTests(unittest.TestCase):
    def call(self, enrollment=None, facts=None, sources=None, digest=DIGEST, now=NOW):
        e, f, s = valid()
        return authorize_candidate(enrollment or e, facts if facts is not None else f,
                                   expected_terms_sha256=digest, now=now,
                                   trusted_sources=sources if sources is not None else s)

    def test_all_proofs_still_nonpayable(self):
        result = self.call()
        self.assertFalse(result["payable"])
        self.assertFalse(result["wallet_request"])
        self.assertFalse(result["credit"])
        self.assertFalse(result["settled"])
        self.assertEqual(len(result["proof_digests"]), 20)

    def test_every_required_proof_fail_closed(self):
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                e, f, s = valid()
                f[name] = replace(f[name], passed=False)
                with self.assertRaises(InvoiceBoundaryRejected):
                    self.call(e, f, s)

    def test_every_missing_proof_fail_closed(self):
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                e, f, s = valid()
                del f[name]
                with self.assertRaises(InvoiceBoundaryRejected):
                    self.call(e, f, s)

    def test_every_wrong_source_fail_closed(self):
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                e, f, s = valid()
                f[name] = replace(f[name], source="browser")
                with self.assertRaises(InvoiceBoundaryRejected):
                    self.call(e, f, s)

    def test_every_expired_proof_fail_closed(self):
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                e, f, s = valid()
                f[name] = replace(f[name], valid_until=NOW)
                with self.assertRaises(InvoiceBoundaryRejected):
                    self.call(e, f, s)

    def test_wrong_sku(self):
        e, f, s = valid()
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(replace(e, product="MOJPROP-STARTER30"), f, s)

    def test_wrong_amount(self):
        e, f, s = valid()
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(replace(e, amount_sun=30_000_001), f, s)

    def test_wrong_network(self):
        e, f, s = valid()
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(replace(e, network="tron-shasta"), f, s)

    def test_unsigned_terms(self):
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(digest="b" * 64)

    def test_not_approved(self):
        e, f, s = valid()
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(replace(e, status="lead"), f, s)

    def test_wrong_enrollment(self):
        e, f, s = valid()
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(replace(e, enrollment_id="MOJPROP01-ABC"), f, s)

    def test_wrong_subject(self):
        e, f, s = valid()
        f["buyer_kyc_passed"] = replace(f["buyer_kyc_passed"], subject="other")
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(e, f, s)

    def test_future_evidence(self):
        e, f, s = valid()
        f["capital_available_verified"] = replace(f["capital_available_verified"], checked_at=NOW + 1)
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(e, f, s)

    def test_extra_proof(self):
        e, f, s = valid()
        f["browser_approved"] = f["authenticated_buyer"]
        with self.assertRaises(InvoiceBoundaryRejected):
            self.call(e, f, s)

if __name__ == "__main__":
    unittest.main()
