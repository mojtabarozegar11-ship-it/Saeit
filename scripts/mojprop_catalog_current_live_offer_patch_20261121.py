"""Produce an exact-pinned catalog CTA candidate; never modify the website.

Read current English static catalog bytes from the authorized host only.
Fail closed on source drift. The optional consent script, page design, original
service listings and every unrelated page must remain byte-identical.
"""
from __future__ import annotations
import hashlib
import re

SOURCE_SHA256 = "33275fc11f578bbf8b6021535504866a7483e40bb840da98c9d5ac0e35455842"
PAGE = "moj-prop/catalog/index.html"
INSERT_BEFORE = b'<section class="process">'
NEW_OFFER = (
    '<section class="hero" id="starter30-offer" aria-labelledby="starter30-heading">'
    '<div class="eyebrow">SEPARATE SIMULATED TRADING CHALLENGE</div>'
    '<h2 id="starter30-heading">Starter 30 — 30 TRX</h2>'
    '<p>Practice a 60-day simulated challenge with a virtual USD 1,000 account. '
    'Review the daily 6% drawdown limit, 3% risk per trade, 4% combined open-position risk '
    'and consistency requirements before joining. This is not real funded brokerage '
    'capital or a guaranteed investment return. The program states a 100% share of '
    'independently verified qualifying trader-earned profit after a successful pass; '
    'actual company-funded payout execution has not been independently established.</p>'
    '<p>Pay only against a unique invoice created by the official checkout. '
    'No customer trading capital is held by Moj Prop.</p>'
    '<p><a class="cta" href="/moj-prop/starter-30-trx/">Review Starter 30 rules</a> '
    '<a href="/mojprop-starter30-checkout/">Check 30 TRX checkout availability</a></p>'
    '</section>'
).encode("utf-8")


def generate_candidate(original: bytes) -> bytes:
    if not isinstance(original, bytes):
        raise TypeError("catalog source must be byte evidence")
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("current-live catalog source drift; no release candidate")
    if original.count(INSERT_BEFORE) != 1:
        raise ValueError("expected single catalog process section")
    if b'/mojprop-starter30-checkout/' in original:
        raise ValueError("public Starter30 checkout already linked; inspect before re-applying")
    if original.count(b'/mpw-measure/tracker.js') != 1:
        raise ValueError("existing optional consent telemetry missing or changed")
    candidate = original.replace(INSERT_BEFORE, NEW_OFFER + INSERT_BEFORE, 1)
    if candidate.replace(NEW_OFFER, b"", 1) != original:
        raise ValueError("unexpected unrelated change")
    for kind in (rb"<script\b[^>]*>.*?</script>", rb"<style\b[^>]*>.*?</style>", rb"<form\b[^>]*>.*?</form>"):
        if re.findall(kind, original, re.I | re.S) != re.findall(kind, candidate, re.I | re.S):
            raise ValueError("protected functional markup changed")
    return candidate
