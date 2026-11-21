"""Exact-byte, fail-closed English Moj Prop payment-page checkout navigation.

The published page lives on cPanel as a static HTML file. This generator never
writes live files; a guarded host release must independently verify old bytes,
private restore, SHA and public HTTP before and after a scoped atomic replacement.
"""
from __future__ import annotations
import hashlib

PAGE = "moj-prop/payment/index.html"
SOURCE_SHA256 = "1ff56cace9e52d2f6cd6a332bf3159cccbfc5ff7cf70a3c87b06ee497d1d1d7e"
CANDIDATE_SHA256 = "498e1ebe2260650c5170c3b577b06878dd3beb295c74f849344643f33ab6b59b"
ORIGINAL_LINKS = ('<p><a href="/moj-prop/starter-30-trx/">Read Starter30 offer</a> · ').encode()
UPDATED_LINKS = (
    '<p><a href="/moj-prop/starter-30-trx/">Read Starter30 offer</a> · '
    '<a href="/mojprop-starter30-checkout/">Review the official 30 TRX checkout form</a> · '
).encode()
PROTECTED_DISCLOSURES = (
    b"Do not transfer funds unless the official server supplies a valid invoice and complete terms.",
    b"Live payout execution and an enforceable payment timetable are not independently established",
    b"/mpw-measure/tracker.js",
)


def generate_candidate(original: bytes) -> bytes:
    if not isinstance(original, bytes):
        raise TypeError("payment static source must be bytes")
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("production static payment source drift")
    if original.count(ORIGINAL_LINKS) != 1:
        raise ValueError("payment link anchor changed")
    if b"/mojprop-starter30-checkout/" in original:
        raise ValueError("checkout link already exists")
    for phrase in PROTECTED_DISCLOSURES:
        if original.count(phrase) != 1:
            raise ValueError("protected disclosure missing/duplicated")
    result = original.replace(ORIGINAL_LINKS, UPDATED_LINKS, 1)
    if result.replace(UPDATED_LINKS, ORIGINAL_LINKS, 1) != original:
        raise ValueError("unrelated content changed")
    for phrase in PROTECTED_DISCLOSURES:
        if result.count(phrase) != 1:
            raise ValueError("protected disclosure changed")
    if hashlib.sha256(result).hexdigest() != CANDIDATE_SHA256:
        raise ValueError("candidate no longer matches published version")
    return result
