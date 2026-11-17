"""Independent reviewer attestation for MOJ-PROP-01 buyer terms.

A separate reviewer must sign the exact buyer-acceptance digest. This
pure verifier does not establish legal identity, KYC, payment or enrollment.
Callers must source reviewer keys from a private trusted key registry.
"""
from hashlib import sha256
import hmac
import json
import re

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_REF = re.compile(r"PROP1-REVIEW-[A-F0-9]{32}\Z")


class ReviewerAttestationClosed(ValueError):
    pass


def verify_independent_reviewer(*, acceptance_digest, review_ref,
                                reviewer_attestation, reviewer_hmac,
                                reviewer_key, acceptance_provider_key,
                                now_sec):
    """Fail closed on unsigned, stale, replay-prone or unbound review evidence.

    This is a cryptographic check only. The caller must separately enforce
    one-time consumption and validate the real reviewer and legal authority.
    """
    if (type(acceptance_digest) is not str or _HEX.fullmatch(acceptance_digest) is None
            or acceptance_digest == "0" * 64
            or type(review_ref) is not str or _REF.fullmatch(review_ref) is None
            or type(reviewer_hmac) is not str or _HEX.fullmatch(reviewer_hmac) is None
            or type(reviewer_key) is not bytes or len(reviewer_key) < 32
            or type(acceptance_provider_key) is not bytes
            or len(acceptance_provider_key) < 32
            or hmac.compare_digest(reviewer_key, acceptance_provider_key)
            or type(now_sec) is not int or now_sec < 1735689600):
        raise ReviewerAttestationClosed("independent reviewer credentials missing")
    if type(reviewer_attestation) is not dict or set(reviewer_attestation) != {
        "schema", "sku", "review_ref", "acceptance_sha256",
        "reviewer_authority_ref", "issued_at_sec", "expires_at_sec",
        "decision",
    }:
        raise ReviewerAttestationClosed("reviewer evidence schema invalid")
    a = reviewer_attestation
    if (a["schema"] != "mojprop.plan1.independent-review.v1"
            or a["sku"] != "MOJ-PROP-01"
            or a["review_ref"] != review_ref
            or a["acceptance_sha256"] != acceptance_digest
            or a["decision"] != "APPROVED_FOR_PRIVATE_REVIEW_ONLY"
            or type(a["reviewer_authority_ref"]) is not str
            or not 8 <= len(a["reviewer_authority_ref"]) <= 96
            or type(a["issued_at_sec"]) is not int
            or type(a["expires_at_sec"]) is not int
            or not a["issued_at_sec"] <= now_sec < a["expires_at_sec"]
            or a["expires_at_sec"] - a["issued_at_sec"] > 3600):
        raise ReviewerAttestationClosed("reviewer evidence not current or not bound")
    raw = json.dumps(a, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(raw) > 2048 or not hmac.compare_digest(
            hmac.new(reviewer_key, raw, sha256).hexdigest(), reviewer_hmac):
        raise ReviewerAttestationClosed("independent reviewer signature invalid")
    return True
