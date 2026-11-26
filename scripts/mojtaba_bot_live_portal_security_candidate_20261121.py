"""Pure, pinned candidate to retire unsafe legacy checkout navigation on live bot.

Captured from the ACTIVE Passenger application template on 2026-11-21,
not a claim that the central bot has been deployed or restarted.
No filesystem writes, live deployment, DB, finance or network operations.
An independently authorized, reversible, *template-only* production release
must verify the original exact-byte digest and create a private rollback first.
"""
from __future__ import annotations

import hashlib

TEMPLATE = "templates/core/mojtaba_bot_portal.html"
ORIGINAL_SHA256 = "c39817f7ac714b69be2920c4d02537096b0a4f18cf35b8bda2de754e36ae56ca"
CANDIDATE_SHA256 = "17b341a62338964f83ef36e8bbcbedac1feaf8e179f73df151bae746cca67ad5"

OLD_GATE = (
    b'      {% if starter30_checkout_available %}\n'
    b'      <p>Online 30 TRX invoice creation is currently enabled by the Moj Prop server. A payment must never be sent until a unique invoice and receiver address have been issued by the checkout itself. Passing the challenge or earning profit is not guaranteed.</p>\n'
    b'      <p><a class="button" href="/mojprop-starter30-checkout/">Open the 30 TRX invoice checkout</a></p>\n'
    b'      {% else %}\n'
    b'      <p class="small">Online invoice creation is not currently offered from this page. You can still request the written conditions without paying.</p>\n'
    b'      {% endif %}\n'
)
SAFE_GATE = (
    b'      <p class="small">Paid Starter30 enrolment is not offered through this portal while invoice controls, payout reserve and buyer eligibility remain unverified. Do not send TRX. Passing a challenge or earning profit is not guaranteed. Request written terms without paying.</p>\n'
)
ORIGINAL_CTA = (
    b'      <a href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx">Request written Starter30 terms</a>\n'
)
SIGNALS_CTA = (
    b'      <p>For a separate educational market brief or signal proposal, request a written scope without payment. This is not a trading order, paid invoice or confirmed signal subscription.</p>\n'
    b'      <a href="/moj-prop-intake/?format=html&amp;service=signals">Request a free written educational signal proposal</a>\n'
)


def generate_candidate(original: bytes) -> bytes:
    """Return a deterministic two-anchor change only, or reject all drift."""
    if type(original) is not bytes:
        raise TypeError("requires exact original raw template bytes")
    if hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("source SHA256 drift: refuse change")
    if original.count(OLD_GATE) != 1 or original.count(ORIGINAL_CTA) != 1:
        raise ValueError("legacy gate or free-terms anchor missing/ambiguous")
    if original.count(b'href="/mojprop-starter30-checkout/"') != 1:
        raise ValueError("legacy checkout anchor mismatch")
    if b'service=signals' in original:
        raise ValueError("signal link already exists; refuse republishing")
    candidate = original.replace(OLD_GATE, SAFE_GATE, 1)
    candidate = candidate.replace(ORIGINAL_CTA, ORIGINAL_CTA + SIGNALS_CTA, 1)
    if candidate.count(SAFE_GATE) != 1 or candidate.count(SIGNALS_CTA) != 1:
        raise ValueError("candidate replacement ambiguous")
    restored = candidate.replace(ORIGINAL_CTA + SIGNALS_CTA, ORIGINAL_CTA, 1)
    restored = restored.replace(SAFE_GATE, OLD_GATE, 1)
    if restored != original:
        raise ValueError("unrelated content changed")
    if b'href="/mojprop-starter30-checkout/"' in candidate:
        raise ValueError("unsafe legacy checkout link survived")
    if hashlib.sha256(candidate).hexdigest() != CANDIDATE_SHA256:
        raise ValueError("candidate SHA256 drift: refuse release")
    return candidate
