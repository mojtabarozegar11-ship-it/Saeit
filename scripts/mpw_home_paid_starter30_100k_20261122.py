#!/usr/bin/env python3
"""Owner-reviewed exact-byte reversible homepage marketing copy patch (nonfinancial).

This command offers --check only. It never writes public files, creates
invoices, changes CRM, restarts Passenger, posts social content, or touches DB.
An authorized atomic cutover must independently verify private backups,
isolate restore proofs and hash-pinned candidate bytes before publication.
"""
import hashlib
import sys
from pathlib import Path

TARGET = Path("/home/zomorod2/mojplaywin.com/design-preview-20261017/production-home-20261017.html")
BEFORE_SHA256 = "0a092406040f739e3815693040f3dddc934e16e7d0749df6490b1af0b389ba48"
AFTER_SHA256 = "eadc94648806f728cf6f559932277d45f61227246c6d4ab992e1949286b4766d"
BEFORE_BYTES = 266250
AFTER_BYTES = 266515

# Only existing static MOJ PROP banner copy and its 5 existing links change.
# The website structure, CSS, 20 translated pages plus official English,
# service navigation and all unrelated products remain untouched.
EDITS = [
  [
    "FEATURED PROGRAM · SIMULATED TRADING",
    "MOJ PROP · 30 TRX ENTRY · SIMULATED TRADING"
  ],
  [
    "MOJ PROP <span>60-Day Trading Challenge</span>",
    "MOJ PROP <span>30 TRX · 14-Level Virtual Pathway</span>"
  ],
  [
    "Starter30 has a listed 30 TRX initial entry. Start with a $1,000 simulated challenge; pass each eligible stage to progress through virtual account levels up to $100,000. Payment is currently unavailable.",
    "Starter30 begins with a $1,000 simulated trading account and a 60-day challenge. Its listed initial entry fee is 30 TRX. Pass each stage and meet the risk and eligibility rules to qualify for the next virtual level, through 14 planned levels up to $100,000. Advancement is conditional, not automatic. Payment is currently unavailable; do not send TRX."
  ],
  [
    "<li>60-day simulation</li><li>$1,000 virtual account</li><li>Risk-first evaluation</li>",
    "<li>30 TRX initial entry</li><li>14 conditional stages</li><li>$1,000 → $100,000 virtual</li>"
  ],
  [
    "<a class=\"mpw-mojprop-primary\" href=\"/moj-prop/\" aria-label=\"Explore the official MOJ PROP English page\">Explore MOJ PROP",
    "<a class=\"mpw-mojprop-primary\" href=\"/moj-prop/starter-30-trx/#scaling-path\" aria-label=\"Review Starter30 entry price and 14 simulated levels\">See 30 TRX Plan &amp; 14 Levels"
  ],
  [
    "<a class=\"mpw-mojprop-secondary\" href=\"/moj-prop/starter-30-trx/\">Read Starter30 terms</a>",
    "<a class=\"mpw-mojprop-secondary\" href=\"/moj-prop/\">MOJ PROP Program Details</a>"
  ],
  [
    "<a class=\"mpw-mojprop-secondary\" href=\"/moj-prop/starter-30-trx/#scaling-path\">30 TRX Starter30 · Levels to $100K</a>",
    "<a class=\"mpw-mojprop-secondary\" href=\"/moj-prop/rules/\">Evaluation &amp; Risk Rules</a>"
  ],
  [
    "Simulated accounts; no customer capital is held. Review the program rules and payment availability before purchasing. No guaranteed earnings.",
    "All $1,000–$100,000 account levels are simulated, not cash or real funded brokerage capital. Progression requires each stage to be passed and verified. Payment is unavailable; earnings are not guaranteed."
  ],
  [
    "<span><b>60</b> DAYS</span><span><b>$1K</b> VIRTUAL</span><span><b>30</b> TRX</span>",
    "<span><b>30</b> TRX ENTRY</span><span><b>14</b> LEVELS</span><span><b>$100K</b> VIRTUAL MAX</span>"
  ]
]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def candidate_bytes(original: bytes) -> bytes:
    if len(original) != BEFORE_BYTES or sha(original) != BEFORE_SHA256:
        raise RuntimeError("REFUSE_HOMEPAGE_BASELINE_DRIFT")
    content = original.decode("utf-8")
    for before, after in EDITS:
        if content.count(before) != 1 or content.count(after):
            raise RuntimeError("COPY_ANCHOR_AMBIGUOUS_OR_ALREADY_MODIFIED")
        content = content.replace(before, after, 1)
    target = content.encode("utf-8")
    if len(target) != AFTER_BYTES or sha(target) != AFTER_SHA256:
        raise RuntimeError("UNREVIEWED_OUTPUT_COPY")
    for before, after in reversed(EDITS):
        if content.count(after) != 1:
            raise RuntimeError("NOT_REVERSIBLE_ANCHOR")
        content = content.replace(after, before, 1)
    if content.encode("utf-8") != original:
        raise RuntimeError("NOT_EXACTLY_REVERSIBLE")
    return target

def check():
    data = TARGET.read_bytes()
    next_data = candidate_bytes(data)
    print("PREVIOUS", len(data), sha(data))
    print("REVIEWED", len(next_data), sha(next_data))
    print("READ_ONLY", True)

if __name__ == "__main__":
    if sys.argv[1:] != ["--check"]:
        raise SystemExit("Only read-only --check is supported")
    check()
