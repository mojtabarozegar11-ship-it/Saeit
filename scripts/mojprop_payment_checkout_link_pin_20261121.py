"""RETIRED: historical pinned generator which added the unsafe 30-TRX checkout.

The actual public English MOJ PROP payment page was already changed to
route future buyers to the free written-terms enquiry. Its earlier static
source has drifted from this obsolete generator's pinned input, and the
effective production WSGI still serves the old, unverified payment POST.

This module is intentionally fail-closed for every input. Never revive
a direct payment link without separately approved, verified exclusive
invoice receivers, written buyer terms and actual company-funded payouts.
The old SHA values remain only as historical provenance evidence.
"""
from __future__ import annotations

import hashlib

PAGE = "moj-prop/payment/index.html"
SOURCE_SHA256 = "1ff56cace9e52d2f6cd6a332bf3159cccbfc5ff7cf70a3c87b06ee497d1d1d7e"
HISTORICAL_UNSAFE_CANDIDATE_SHA256 = "498e1ebe2260650c5170c3b577b06878dd3beb295c74f849344643f33ab6b59b"
RETIRED_REASON = "legacy_checkout_link_generator_retired_until_verified_paid_admission"


def generate_candidate(original: bytes) -> bytes:
    """No-op in production terms: refuse old-source drift and every release."""
    if not isinstance(original, bytes):
        raise TypeError("payment static source must be bytes")
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("production static payment source drift")
    raise RuntimeError(RETIRED_REASON)
