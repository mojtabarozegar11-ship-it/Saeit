"""No-network/no-payment adversarial tests of authenticated real Plan1 B->C handoff."""
import hmac
import unittest
from dataclasses import replace
from hashlib import sha256

from services.mojprop_real_plan1_invoice_boundary import REQUIRED_PROOFS
from services.mojprop_plan1_trusted_handoff import (
    ReviewSnapshot, SignedFact, TrustedAuthority, HandoffRejected,
    _signed_bytes, _B_REVIEW_SCOPE, _C_FACT_SCOPE,
    review_authenticated_preorder, validate_signed_b_review,
)

NOW = 1_800_000_000
ORDER = "MOJPROP01-ABCDEFGHIJKL"
BUYER = "buyer-01234567"
SELLER = "merchant-0001"
TERMS = "a" * 64
REVIEW_KEY = b"B" * 32


def sign_review(review, key=REVIEW_KEY):
    return replace(
        review, signature_hex=hmac.new(
            key, _signed_bytes(_B_REVIEW_SCOPE, review), sha256
        ).hexdigest()
    )


def sign_fact(fact, secret):
    return replace(
        fact, signature_hex=hmac.new(
            secret, _signed_bytes(_C_FACT_SCOPE, fact), sha256
        ).hexdigest()
    )


def valid():
    review = sign_review(ReviewSnapshot(
        order_ref=ORDER, review_ref="PROP1-REVIEW-" + "A" * 32,
        original_request_ref="REQUEST-ABCDEFGH", buyer_id=BUYER,
        seller_id=SELLER, sku="MOJ-PROP-01",
        terms_version="2026-11-15/v1.2", chain="TRON-mainnet",
        token_symbol="TRX", amount_sun=30_000_000,
        signed_terms_sha256=TERMS, contract_pdf_sha256="b" * 64,
        refund_disclosure_sha256="c" * 64,
        buyer_signature_proof_sha256="d" * 64,
        seller_signature_proof_sha256="e" * 64,
        reviewer_packet_sha256="f" * 64,
        issued_at_sec=NOW - 60, expires_at_sec=NOW + 3600,
        state="PRIVATE_NONPAYABLE_CONTRACT_REVIEW",
        payable=False, invoice_created=False,
        settlement_verified=False, enrollment_created=False,
        signature_hex=""
    ))
    authorities = {
        name: TrustedAuthority("trusted-svc-" + str(i), "key-" + str(i),
                               bytes([i + 1]) * 32)
        for i, name in enumerate(REQUIRED_PROOFS)
    }
    facts = {
        name: sign_fact(SignedFact(
            name=name, issuer=authorities[name].issuer,
            key_id=authorities[name].key_id,
            subject=ORDER, buyer_id=BUYER, passed=True,
            evidence_sha256=sha256(name.encode()).hexdigest(),
            checked_at=NOW - 60, valid_until=NOW + 1200, signature_hex="",
        ), authorities[name].secret)
        for name in REQUIRED_PROOFS
    }
    return dict(
        review=review, order_ref=ORDER, buyer_id=BUYER, seller_id=SELLER,
        reviewer_key=REVIEW_KEY, signed_facts=facts,
        authorities=authorities, independent_terms_sha256=TERMS, now=NOW,
    )


class Plan1TrustedHandoffTests(unittest.TestCase):
    def reject(self, **overrides):
        args = valid()
        args.update(overrides)
        with self.assertRaises(HandoffRejected):
            review_authenticated_preorder(**args)

    def test_happy_path_is_still_nonpayable_and_has_zero_wallet_or_txid(self):
        out = review_authenticated_preorder(**valid())
        self.assertEqual(out["independently_signed_proof_count"], 20)
        self.assertEqual(out["status"], "PREPURCHASE_REVIEW_ONLY")
        self.assertEqual(out["product"], "MOJ-PROP-01")
        self.assertEqual(out["amount_sun"], 30_000_000)
        self.assertEqual(out["network"], "tron-mainnet")
        for key in ("payment_invoice_created", "payable", "wallet_request",
                    "customer_credit", "chain_finality_verified",
                    "global_txid_ledger_committed", "enrollment_created",
                    "challenge_activated", "customer_receipt_signed",
                    "refund_executed"):
            self.assertIs(out[key], False, key)
        self.assertNotIn("wallet_address", out)
        self.assertNotIn("txid", out)
        self.assertNotIn("checkout_url", out)

    def test_idempotent_review_audit_digest(self):
        self.assertEqual(review_authenticated_preorder(**valid())["audit_sha256"],
                         review_authenticated_preorder(**valid())["audit_sha256"])

    def test_b_review_signature_tampering(self):
        a = valid()
        self.reject(review=replace(a["review"], signature_hex="a" * 64))

    def test_b_review_wrong_key(self):
        self.reject(reviewer_key=b"Z" * 32)

    def test_b_review_short_key(self):
        self.reject(reviewer_key=b"short")

    def test_b_review_missing_signature(self):
        a = valid()
        self.reject(review=replace(a["review"], signature_hex=""))

    def test_b_review_invalid_digest(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], contract_pdf_sha256="0" * 64)))

    def test_b_review_unsigned_customer_signature(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], buyer_signature_proof_sha256="")))

    def test_b_review_unsigned_seller_signature(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], seller_signature_proof_sha256="")))

    def test_b_review_missing_refund_disclosure(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], refund_disclosure_sha256="")))

    def test_b_review_wrong_sku_even_if_signed(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], sku="MOJPROP-STARTER30")))

    def test_b_review_wrong_amount_even_if_signed(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], amount_sun=30_000_001)))

    def test_b_review_wrong_network_even_if_signed(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], chain="Nile")))

    def test_b_review_wrong_token_even_if_signed(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], token_symbol="USDT")))

    def test_b_review_wrong_version_even_if_signed(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], terms_version="v1.1")))

    def test_b_review_does_not_mean_invoice_issued(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], invoice_created=True)))

    def test_b_review_cannot_claim_settlement(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], settlement_verified=True)))

    def test_b_review_cannot_claim_enrollment_created(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], enrollment_created=True)))

    def test_b_review_false_like_integer_does_not_pass(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], payable=0)))

    def test_b_review_wrong_status(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], state="PAID")))

    def test_b_review_expired(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], expires_at_sec=NOW)))

    def test_b_review_not_yet_issued(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], issued_at_sec=NOW + 1)))

    def test_b_review_excessive_duration(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], issued_at_sec=NOW-90000)))

    def test_b_review_order_mismatch(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], order_ref="MOJPROP01-ZZZZZZZZZZZZ")))

    def test_b_review_customer_mismatch(self):
        self.reject(buyer_id="different-buyer")

    def test_b_review_seller_mismatch(self):
        self.reject(seller_id="merchant-OTHER")

    def test_b_review_bad_review_ref(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], review_ref="LEAD-1234")))

    def test_b_review_bad_request_ref(self):
        a = valid()
        self.reject(review=sign_review(replace(a["review"], original_request_ref="x")))

    def test_b_review_bad_order_ref(self):
        self.reject(order_ref="MOJPROP-INVALID")

    def test_independent_terms_required(self):
        self.reject(independent_terms_sha256="b" * 64)

    def test_independent_terms_empty_not_accepted(self):
        self.reject(independent_terms_sha256="")

    def test_review_payer_facts_not_taken_from_browser(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = replace(f[name], signature_hex="0" * 64)
        self.reject(signed_facts=f)

    def test_all_20_individual_negative_gates(self):
        a = valid()
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                f = a["signed_facts"].copy()
                f[name] = sign_fact(replace(f[name], passed=False),
                                    a["authorities"][name].secret)
                self.reject(signed_facts=f)

    def test_all_20_expired_proofs(self):
        a = valid()
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                f = a["signed_facts"].copy()
                f[name] = sign_fact(replace(f[name], valid_until=NOW),
                                    a["authorities"][name].secret)
                self.reject(signed_facts=f)

    def test_all_20_missing_proofs(self):
        a = valid()
        for name in REQUIRED_PROOFS:
            with self.subTest(name=name):
                f = a["signed_facts"].copy()
                del f[name]
                self.reject(signed_facts=f)

    def test_missing_authority(self):
        a = valid()
        authorities = a["authorities"].copy()
        del authorities[REQUIRED_PROOFS[0]]
        self.reject(authorities=authorities)

    def test_extra_authority(self):
        a = valid()
        authorities = a["authorities"].copy()
        authorities["browser"] = authorities[REQUIRED_PROOFS[0]]
        self.reject(authorities=authorities)

    def test_extra_fact(self):
        a = valid()
        f = a["signed_facts"].copy()
        f["browser"] = f[REQUIRED_PROOFS[0]]
        self.reject(signed_facts=f)

    def test_fact_wrong_buyer_with_valid_signature(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], buyer_id="buyer-other"),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_wrong_order_with_valid_signature(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], subject="MOJPROP01-ZZZZZZZZZZZZ"),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_wrong_source_with_valid_signature(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], issuer="browser"),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_wrong_key_id_with_valid_signature(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], key_id="browser"),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_future_dated(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], checked_at=NOW+1),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_zero_digest(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], evidence_sha256="0" * 64),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_lifetime_cannot_exceed_day(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], valid_until=NOW+90000),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_fact_cannot_reuse_same_key_across_independent_sources(self):
        a = valid()
        authorities = a["authorities"].copy()
        name1, name2 = REQUIRED_PROOFS[:2]
        authorities[name2] = replace(authorities[name2], secret=authorities[name1].secret)
        self.reject(authorities=authorities)

    def test_fact_cannot_reuse_same_issuer_key_id(self):
        a = valid()
        authorities = a["authorities"].copy()
        name1, name2 = REQUIRED_PROOFS[:2]
        authorities[name2] = replace(
            authorities[name2], issuer=authorities[name1].issuer,
            key_id=authorities[name1].key_id,
        )
        self.reject(authorities=authorities)

    def test_fact_cannot_share_reviewer_key(self):
        a = valid()
        authorities = a["authorities"].copy()
        name = REQUIRED_PROOFS[0]
        authorities[name] = replace(authorities[name], secret=REVIEW_KEY)
        self.reject(authorities=authorities)

    def test_fact_cannot_use_short_secret(self):
        a = valid()
        authorities = a["authorities"].copy()
        name = REQUIRED_PROOFS[0]
        authorities[name] = replace(authorities[name], secret=b"weak")
        self.reject(authorities=authorities)

    def test_fact_must_be_boolean_true_not_integer_one(self):
        a = valid()
        f = a["signed_facts"].copy()
        name = REQUIRED_PROOFS[0]
        f[name] = sign_fact(replace(f[name], passed=1),
                            a["authorities"][name].secret)
        self.reject(signed_facts=f)

    def test_reviewer_key_does_not_prove_document_legality(self):
        a = valid()
        # This is a signed snapshot only; output has no legal license attestation.
        out = review_authenticated_preorder(**a)
        self.assertNotIn("legal_sale_authorized", out)
        self.assertNotIn("contract_legally_enforceable", out)
        self.assertFalse(out["payable"])

    def test_authoritative_enrollment_is_not_created_by_prepayment(self):
        out = review_authenticated_preorder(**valid())
        self.assertFalse(out["enrollment_created"])
        self.assertFalse(out["customer_credit"])
        self.assertFalse(out["chain_finality_verified"])


if __name__ == "__main__":
    unittest.main()
