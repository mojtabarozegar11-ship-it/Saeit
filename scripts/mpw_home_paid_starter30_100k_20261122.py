#!/usr/bin/env python3
"""Source-reviewed, read-only, exact-byte static MojPlayWin home offer patch.

This module NEVER writes files or triggers a release. Its candidate_bytes()
function can be imported by a separately approved owner-scoped static HTML
release with private backup, isolated file restore, atomic swap and rollback.
No DB, payment, Passenger, factory, social or API side effects.
"""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

TARGET=Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
BEFORE_SHA256="a353201a6e8d5b7bc3ec6d22f3387b9da051c7e655a40fbd8a9d99481c2fe435"
AFTER_SHA256="0a092406040f739e3815693040f3dddc934e16e7d0749df6490b1af0b389ba48"
BEFORE_BYTES=266345
AFTER_BYTES=266250

EDITS=(
    (
        "Explore a structured simulated trading evaluation with a $1,000 virtual reference account, transparent risk limits and a 30 TRX Starter30 option.",
        "Starter30 has a listed 30 TRX initial entry. Start with a $1,000 simulated challenge; pass each eligible stage to progress through virtual account levels up to $100,000. Payment is currently unavailable.",
    ),
    (
        'href="/moj-prop-intake/?format=html&amp;service=blueprint&amp;package=starter-30-trx&amp;utm_source=moj_prop&amp;utm_medium=onsite&amp;utm_campaign=starter30_lead&amp;utm_content=free_terms">Request free Starter30 written terms',
        'href="/moj-prop/starter-30-trx/#scaling-path">30 TRX Starter30 · Levels to $100K',
    ),
    (
        '>Request free Signal Desk terms</a>',
        '>Signal Desk information</a>',
    ),
)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def candidate_bytes(original:bytes)->bytes:
    if len(original)!=BEFORE_BYTES or sha(original)!=BEFORE_SHA256:
        raise RuntimeError("REFUSE_STATIC_HOME_SOURCE_SHA_DRIFT")
    try:
        text=original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("INVALID_ORIGINAL_UTF8") from exc
    result=text
    for before,after in EDITS:
        if result.count(before)!=1 or result.count(after)!=0:
            raise RuntimeError("COPY_ANCHOR_NOT_UNIQUE_OR_ALREADY_CHANGED")
        result=result.replace(before,after,1)
    new=result.encode("utf-8")
    if len(new)!=AFTER_BYTES or sha(new)!=AFTER_SHA256:
        raise RuntimeError("REVIEWED_STATIC_HOME_CANDIDATE_MISMATCH")
    for before,after in reversed(EDITS):
        if result.count(after)!=1:
            raise RuntimeError("COPY_ROLLBACK_ANCHOR_MISSING")
        result=result.replace(after,before,1)
    if result.encode("utf-8")!=original:
        raise RuntimeError("COPY_NOT_EXACTLY_REVERSIBLE")
    return new

def check_readonly():
    before=TARGET.read_bytes()
    after=candidate_bytes(before)
    print("REVIEWED_NONFINANCIAL_STATIC_HOME",len(before),sha(before))
    print("NEW_COPY",len(after),sha(after))
    print("NO_FILE_WRITES",True)

if __name__=="__main__":
    if sys.argv[1:]!=["--check"]:
        raise SystemExit("Only --check is supported; no deployment side effects")
    check_readonly()
