"""Exact-byte pure candidate for a *separately authorized* live signals CTA.

This module NEVER writes live files, restarts Passenger, creates CRM requests
or takes payment. The original source was inspected on the real English
mojplaywin.com/moj-prop/signals/ static HTML file on 21 November 2026.
Any different source bytes or duplicate navigation fail closed.
"""
from __future__ import annotations

import hashlib

PAGE = "moj-prop/signals/index.html"
SOURCE_SHA256 = "34b05a98ec6fa1eee9d8c340c7cc72a400e109aa712cc113da446f28661720b0"
CANDIDATE_SHA256 = "88cc091c8238da7362da4cea957773edcaf503bf4f7fbaacf92b3b7e42d253c0"

ORIGINAL = b'<a href="/moj-prop/#request">Start a request</a></nav>'
REPLACEMENT = (
    b'<a href="/moj-prop/#request">Start a request</a>'
    b'<a href="/moj-prop-intake/?format=html&amp;service=signals">'
    b'Request a free written signal proposal</a></nav>'
)


def generate_candidate(original: bytes) -> bytes:
    """Pure byte transformation; requires an independent host release gate."""
    if not isinstance(original, bytes):
        raise TypeError("source must be raw HTML bytes")
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("source SHA256 drift; refuse update")
    if original.count(ORIGINAL) != 1:
        raise ValueError("source navigation anchor ambiguous")
    if b'/moj-prop-intake/?format=html&amp;service=signals' in original:
        raise ValueError("signal request link already exists")
    if b'/mojprop-starter30-checkout/' in original:
        raise ValueError("old TRX checkout link found; refuse mutation")
    candidate = original.replace(ORIGINAL, REPLACEMENT, 1)
    if candidate.count(REPLACEMENT) != 1:
        raise ValueError("candidate navigation anchor ambiguous")
    if candidate.replace(REPLACEMENT, ORIGINAL, 1) != original:
        raise ValueError("unrelated HTML changed")
    if hashlib.sha256(candidate).hexdigest() != CANDIDATE_SHA256:
        raise ValueError("candidate drift; no release")
    return candidate
