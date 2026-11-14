#!/usr/bin/env python3
"""Offline revenue channel and funnel triage for the ONE mojtaba.bot.ai.

Source and synthetic business planning only. No sale, quote, customer record,
settlement, bot process, network request, email or website publication occurs.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path

BOT = "mojtaba.bot.ai"
SCHEMA = "mojtaba.bot.ai.revenue-portfolio.source-preview.v1"
# These are candidate models, not assertions of deployed products or legal payment paths.
CANDIDATES = (
    ("website_checkout_repair", "service", "mojplaywin.com", "draft_inquiry_source"),
    ("farm_break_even", "service", "zomorodmelal.ir", "draft_inquiry_source"),
    ("research_consulting", "service", "zomorodmelal.ir", "candidate_unverified"),
    ("digital_books", "digital_product", "zomorodmelal.ir", "candidate_unverified"),
    ("english_digital_guides", "digital_product", "mojplaywin.com", "candidate_unverified"),
    ("training", "training", "zomorodmelal.ir", "candidate_unverified"),
    ("licensed_templates", "licensing", "mojplaywin.com", "candidate_unverified"),
    ("subscriptions", "subscription", "mojplaywin.com", "candidate_unverified"),
    ("sponsorship", "sponsorship", "mojplaywin.com", "candidate_unverified"),
    ("b2b_supply", "physical_goods", "zomorodmelal.ir", "candidate_unverified"),
    ("game_content", "game_digital", "mojplaywin.com", "candidate_unverified"),
)
GATES = (
    "source_and_rights", "verified_deliverable", "owner_price_approval",
    "lawful_payment_and_tax", "refund_terms", "customer_support_route",
    "real_live_route", "receipt_to_delivery_test",
)
FUNNEL_KEYS = ("views", "inquiries", "qualified", "approved_quotes",
               "settled_orders", "delivered_orders")


def catalogue() -> dict:
    """Prioritized only by existing *repository* source, never by claimed sales."""
    items = []
    for code, model, domain, source in CANDIDATES:
        items.append({
            "code": code, "model": model, "site": domain,
            "canonical_bot": BOT, "source_status": source,
            "priority": "review_existing_draft" if source == "draft_inquiry_source"
                        else "verify_candidate_first",
            "missing_verified_gates": list(GATES),
            "commercial_release": "blocked_unverified",
            "revenue_collected": None,
            "autonomous_payment": False, "auto_contact": False,
        })
    return {
        "schema": SCHEMA, "canonical_bot": BOT,
        "scope": "repository_source_only_not_live",
        "existing_draft_inquiry_count": sum(
            x[3] == "draft_inquiry_source" for x in CANDIDATES
        ),
        "candidate_model_count": len(CANDIDATES),
        "commercially_verified_count": None, "collected_revenue": None,
        "items": items,
    }


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def funnel(source: dict) -> dict:
    """Compute SYNTHETIC same-cohort ratios only; never infer actual revenue."""
    if not isinstance(source, dict) or set(source) != {"schema", "synthetic_example", "counts"}:
        raise ValueError("expected synthetic aggregate with exact allowed keys")
    if source["schema"] != "mojtaba.bot.ai.synthetic-funnel.v1" or source["synthetic_example"] is not True:
        raise ValueError("real unverified customer telemetry prohibited")
    counts = source["counts"]
    if not isinstance(counts, dict) or set(counts) != set(FUNNEL_KEYS):
        raise ValueError("counts need the six exact non-identifying funnel fields")
    values = []
    for key in FUNNEL_KEYS:
        n = counts[key]
        if type(n) is not int or not 0 <= n <= 1_000_000_000:
            raise ValueError("invalid aggregate count: " + key)
        values.append(n)
    if any(a < b for a, b in zip(values, values[1:])):
        raise ValueError("same-cohort funnel is not monotone")
    def rate(numer: int, denom: int):
        if denom == 0:
            return None
        return str((Decimal(numer) / Decimal(denom) * 100).quantize(Decimal("0.01")))
    return {
        "schema": "mojtaba.bot.ai.synthetic-funnel-report.v1",
        "canonical_bot": BOT, "synthetic_example": True,
        "population": "same_cohort_synthetic_only",
        "ratios_percent": {
            "inquiry": rate(values[1], values[0]),
            "qualification": rate(values[2], values[1]),
            "quote": rate(values[3], values[2]),
            "settled_order_per_quote": rate(values[4], values[3]),
            "delivery_per_settled_order": rate(values[5], values[4]),
        },
        "counts": dict(zip(FUNNEL_KEYS, values)),
        "real_revenue": None, "real_conversion_rates": None,
        "automated_sales_enabled": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One-bot, offline, noncommercial revenue triage")
    p.add_argument("--catalogue", action="store_true", help="Show source-only model candidates")
    p.add_argument("--synthetic-funnel", help="Local synthetic, PII-free JSON file")
    a = p.parse_args(argv)
    if a.catalogue == bool(a.synthetic_funnel):
        p.error("choose exactly one of --catalogue or --synthetic-funnel")
    if a.catalogue:
        result = catalogue()
    else:
        path = Path(a.synthetic_funnel)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
            p.error("synthetic file must be a regular non-symlink file of at most 16 KiB")
        try:
            result = funnel(json.loads(path.read_text(encoding="utf-8"),
                                      object_pairs_hook=_unique_pairs,
                                      parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("nonfinite JSON"))))
        except (ValueError, UnicodeError) as exc:
            p.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
