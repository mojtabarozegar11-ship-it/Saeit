#!/usr/bin/env python3
"""Inspect only repository files; no browser, network, purchase or deployment."""
from pathlib import Path
from mojtaba_revenue_portfolio import CANONICAL_BOT, OFFERS

ROOT = Path(__file__).resolve().parents[1]
MUST_HAVE = {
    "core/templates/core/services.html": (
        'id="farm-break-even-inquiry"', 'href="/contact/"',
    ),
    "core/templates/mojplaywin/section.html": (
        'id="website-checkout-inquiry"', "mailto:mojplaywin@gmail.com",
    ),
    "core/templates/brands/mojplaywin/page.html": (
        'id="website-checkout-inquiry"', "mailto:mojplaywin@gmail.com",
    ),
}


def audit():
    missing = []
    for offer in OFFERS.values():
        if not (ROOT / offer.source).is_file():
            missing.append("OFFER_SOURCE_MISSING:" + offer.code)
    for rel, markers in MUST_HAVE.items():
        path = ROOT / rel
        if not path.is_file():
            missing.append("CTA_SOURCE_MISSING:" + rel)
            continue
        content = path.read_text(encoding="utf-8")
        for marker in markers:
            if content.count(marker) != 1:
                missing.append("CTA_MARKER_COUNT_INVALID:" + rel + ":" + marker)
    return {
        "schema": "mojtaba.bot.ai.source-only-audit.v1",
        "canonical_bot": CANONICAL_BOT,
        "offer_source_paths_checked": len(OFFERS),
        "service_cta_templates_checked": len(MUST_HAVE),
        "missing_source_contracts": missing,
        "source_contract_ok": not missing,
        "live_render_verified": False,
        "delivery_verified": False,
        "revenue_verified": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
    raise SystemExit(0 if audit()["source_contract_ok"] else 1)
