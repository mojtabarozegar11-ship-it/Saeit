#!/usr/bin/env python3
"""Read-only, privacy-minimized MojPlayWin + MOJ PROP funnel report.
Raw session tokens never appear in output. No Django import or database access.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

ROOT = Path("/home/zomorod2/.mpw-measure/events")
SITES = ("store", "prop")
EVENTS = frozenset(("page", "engaged", "product_click", "plan_click",
                    "buy_click", "form_submit", "help_click", "lead_click"))
PAGE_SETS = {
    "store": {
        "/store/", "/store/product/", "/commerce/trx-easy/", "/commerce/book/",
        "/commerce/trx-easy/invoice/", "/commerce/trx-easy/purchases/",
        "/commerce/trx-easy/recover/",
    },
    "prop": {
        "/moj-prop/", "/moj-prop/starter-30-trx/", "/moj-prop/payment/",
        "/moj-prop/catalog/", "/moj-prop/rules/", "/moj-prop/contact/",
        "/moj-prop/signals/",
        "/mojprop-starter30-checkout/",
    },
}
ENTRY = {"store": "/store/", "prop": "/moj-prop/"}
CHECKOUT = {"store": "/commerce/book/", "prop": "/mojprop-starter30-checkout/"}


def load_events(root: Path, days: int, now=None):
    now = now or datetime.now(timezone.utc)
    records = []
    invalid = 0
    for offset in range(days):
        date = (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        file = root / (date + ".jsonl")
        if not file.is_file() or file.is_symlink():
            continue
        with file.open("r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    x = json.loads(line)
                    if (not isinstance(x, dict) or x.get("site") not in SITES
                            or x.get("event") not in EVENTS
                            or x.get("page") not in PAGE_SETS[x["site"]]
                            or not isinstance(x.get("session"), str)
                            or len(x["session"]) != 32
                            or any(c not in "0123456789abcdef" for c in x["session"])):
                        invalid += 1
                        continue
                    records.append(x)
                except (json.JSONDecodeError, TypeError, KeyError):
                    invalid += 1
    return records, invalid


def summarize(records, days: int, invalid: int = 0):
    result = {
        "schema": "mpw.measure.funnel.v1",
        "window_days": days,
        "data_status": "recorded_opt_in_events_only",
        "human_classification": "engagement_proxy_not_verified_person",
        "paid_orders": None,
        "paid_orders_note": "Paid orders require authoritative server-side settlement evidence; client events are never sales.",
        "ignored_invalid_lines": invalid,
        "sites": {},
    }
    for site in SITES:
        events = [x for x in records if x["site"] == site]
        sessions = defaultdict(list)
        for e in events:
            sessions[e["session"]].append(e)
        qualified = {
            sid for sid, rows in sessions.items()
            if any(x["event"] in ("engaged", "buy_click", "lead_click", "form_submit") for x in rows)
        }
        entry = {
            sid for sid, rows in sessions.items()
            if any(x["event"] == "page" and x["page"] == ENTRY[site] for x in rows)
        }
        entry_qualified = entry & qualified
        buys = {
            sid for sid, rows in sessions.items()
            if any(x["event"] == "buy_click" for x in rows)
        }
        leads = {
            sid for sid, rows in sessions.items()
            if any(x["event"] == "lead_click" for x in rows)
        }
        checkout = {
            sid for sid, rows in sessions.items()
            if any(x["event"] == "page" and x["page"] == CHECKOUT[site] for x in rows)
        }
        forms = {
            sid for sid, rows in sessions.items()
            if any(x["event"] == "form_submit" for x in rows)
        }
        source = Counter()
        for sid in qualified:
            attrs = [x.get("source", "") for x in sessions[sid] if x.get("source")]
            source[attrs[0] if attrs else "direct_or_unknown"] += 1
        visitors = len(sessions)
        result["sites"][site] = {
            "events": dict(Counter(x["event"] for x in events)),
            "opt_in_sessions": visitors,
            "qualified_engaged_sessions": len(qualified),
            "entry_page_sessions": len(entry),
            "qualified_entry_sessions": len(entry_qualified),
            "buy_click_sessions": len(buys),
            "written_terms_lead_click_sessions": len(leads),
            "buy_clicks_from_qualified_entry": len(entry_qualified & buys),
            "checkout_page_sessions": None,
            "checkout_page_coverage": "not_instrumented: Django checkout retains script-src none",
            "form_submit_sessions": len(forms),
            "qualified_entry_without_buy_click": len(entry_qualified - buys),
            "qualified_entry_to_buy_click_rate_pct": round(
                100 * len(entry_qualified & buys) / len(entry_qualified), 1
            ) if entry_qualified else None,
            "qualified_entry_dropoff_proxy_pct": round(
                100 * len(entry_qualified - buys) / len(entry_qualified), 1
            ) if entry_qualified else None,
            "engaged_sessions_by_utm_source": dict(source.most_common(20)),
            "limitations": (
                "Consent is optional, and a session means one consenting browser tab for <=30 minutes. "
                "Missing next step is a drop-off proxy, not proof of abandonment. "
                "Bot filtering is heuristic; script-blocked visits are omitted. "
                "Django checkout pages intentionally disallow injected scripts. "
                "Payment and delivery require the verified back-office ledger."
            ),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if not 1 <= args.days <= 30:
        parser.error("--days must be 1..30")
    rows, invalid = load_events(args.root, args.days)
    print(json.dumps(summarize(rows, args.days, invalid), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
