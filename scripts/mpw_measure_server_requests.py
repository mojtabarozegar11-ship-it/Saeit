#!/usr/bin/env python3
"""Read-only aggregated server request counts for MojPlayWin/English MOJ PROP.

Not a unique-human counter, session tracker, consent bypass, or sale verifier.
Never prints or persists IPs, user agents, referrers, raw query strings, IDs,
cookies or access-log lines. Reads only bounded known cPanel log filenames.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import re

CURRENT_LOG = Path("/home/zomorod2/access-logs/mojplaywin.com.zomorodmelal.ir-ssl_log")
ARCHIVE_DIR = Path("/home/zomorod2/logs")
ARCHIVE_PREFIX = "mojplaywin.com.zomorodmelal.ir-ssl_log-"


def discover_logs(now, days):
    """Pinned domain, rolling calendar months; no directory-wide log crawling."""
    start = now - timedelta(days=days + 2)  # cover local-month offset
    month = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    end = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    paths = [CURRENT_LOG]
    while month <= end:
        paths.append(ARCHIVE_DIR / (ARCHIVE_PREFIX + month.strftime("%b-%Y") + ".gz"))
        year, m = (month.year + 1, 1) if month.month == 12 else (month.year, month.month + 1)
        month = datetime(year, m, 1, tzinfo=timezone.utc)
        if len(paths) > 5:
            raise ValueError("TOO_MANY_LOG_MONTHS")
    return tuple(paths)
REQUEST = re.compile(r'^([A-Z]+) ([^ ]+) HTTP/[0-9.]+$')
TIMESTAMP = re.compile(r'\[([0-9]{2}/[A-Za-z]{3}/[0-9]{4}:[0-9]{2}:[0-9]{2}:[0-9]{2} [+-][0-9]{4})\]')
AUTOMATION = re.compile(
    r'bot|spider|crawler|curl|wget|python|httpclient|headless|uptime|healthcheck|'
    r'pingdom|monitor|scrapy|lighthouse|google|bing|yandex|ahrefs|semrush|'
    r'facebookexternalhit|preview|siteaudit', re.IGNORECASE
)
BROWSER = re.compile(r'Mozilla/5\.0|Chrome/|Firefox/|Safari/', re.IGNORECASE)
SUFFIX_ID = r'[1-9][0-9]*'


def stage(path: str):
    """Return (site, stage) for public routes only; discard dynamic IDs."""
    exact = {
        "/store/": ("store", "landing"),
        "/commerce/trx-easy/": ("store", "public_catalog"),
        "/commerce/trx-easy/purchases/": ("store", "purchases"),
        "/commerce/trx-easy/recover/": ("store", "recovery"),
        "/moj-prop/": ("prop", "landing"),
        "/moj-prop/starter-30-trx/": ("prop", "starter30"),
        "/moj-prop/catalog/": ("prop", "catalog"),
        "/moj-prop/rules/": ("prop", "rules"),
        "/moj-prop/payment/": ("prop", "payment_info"),
        "/moj-prop/contact/": ("prop", "contact"),
        "/moj-prop/signals/": ("prop", "signals"),
        "/mojprop-starter30-checkout/": ("prop", "checkout_request"),
    }
    if path in exact:
        return exact[path]
    dynamic = (
        # Only currently advertised legacy SKUs; scanner sentinel IDs are
        # deliberately excluded so they cannot masquerade as lost buyers.
        (r'/store/product/(?:72|225|879)/checkout/', ("store", "legacy_checkout")),
        (r'/store/product/' + SUFFIX_ID + r'/', ("store", "product")),
        (r'/commerce/book/' + SUFFIX_ID + r'/', ("store", "checkout_request")),
        (r'/commerce/trx-easy/start/' + SUFFIX_ID + r'/', ("store", "start_submission")),
        (r'/commerce/trx-easy/invoice/' + SUFFIX_ID + r'/', ("store", "invoice_page")),
        (r'/commerce/trx-easy/status/' + SUFFIX_ID + r'/', ("store", "status_page")),
        (r'/commerce/trx-easy/reconcile/' + SUFFIX_ID + r'/', ("store", "reconcile_submission")),
        (r'/commerce/trx-easy/download/' + SUFFIX_ID + r'/', ("store", "download_request")),
    )
    for pattern, value in dynamic:
        if re.fullmatch(pattern, path):
            return value
    return None


def parse_line(line: str):
    """Apache combined log parsing, without returning personal identifiers."""
    parts = line.split('"')
    if len(parts) < 6:
        return None
    m = TIMESTAMP.search(parts[0])
    request = REQUEST.match(parts[1])
    if not m or not request:
        return None
    try:
        occurred = datetime.strptime(m.group(1), "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
        code = int(parts[2].strip().split()[0])
    except (ValueError, IndexError):
        return None
    method, target = request.groups()
    if not target.startswith("/"):
        return None
    target = target.split("?", 1)[0]
    match = stage(target)
    if match is None or method not in ("GET", "POST", "HEAD") or not 100 <= code <= 599:
        return None
    agent = parts[5]
    category = "likely_automated" if AUTOMATION.search(agent) else (
        "browser_like_unverified" if BROWSER.search(agent) else "unknown_agent"
    )
    return occurred, match[0], match[1], method, code, category


def summarize(logs=None, days=7, now=None):
    now = now or datetime.now(timezone.utc)
    if logs is None:
        logs = discover_logs(now, days)
    since = now - timedelta(days=days)
    counts = defaultdict(Counter)
    statuses = defaultdict(Counter)
    source_sizes = {}
    skipped = 0
    for path in logs:
        if not path.is_file() or path.is_symlink():
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        source_sizes[path.name] = path.stat().st_size
        try:
            with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    item = parse_line(line)
                    if item is None:
                        skipped += 1
                        continue
                    when, site, point, method, code, classification = item
                    if not since <= when <= now:
                        continue
                    # Redirects, 4xx, and 5xx matter for diagnosing checkout failure.
                    name = site + "/" + point
                    counts[name][method + "_" + str(code) + "_" + classification] += 1
                    statuses[name][str(code)[0] + "xx"] += 1
        except (OSError, EOFError, ValueError):
            skipped += 1
    report = {
        "schema": "mpw.measure.server_requests.v1",
        "window_days": days,
        "time_end_utc": now.isoformat(),
        "time_start_utc": since.isoformat(),
        "scope": "addon_domain_access_logs_only",
        "data_type": "aggregated_http_requests_not_unique_people",
        "verified_human_visitors": None,
        "verified_customer_purchases": None,
        "click_to_buy_conversion_rate": None,
        "source_log_size_bytes": source_sizes,
        "unparsed_or_out_of_scope_lines": skipped,
        "stages": {},
    }
    for name in sorted(counts):
        event_counts = counts[name]
        report["stages"][name] = {
            "get_200_browser_like_unverified": event_counts.get("GET_200_browser_like_unverified", 0),
            "get_404_requests": sum(n for k, n in event_counts.items() if k.startswith("GET_404_")),
            "get_30x_redirects": sum(n for k, n in event_counts.items() if k.startswith(("GET_301_", "GET_302_", "GET_307_", "GET_308_"))),
            "get_200_likely_automated": event_counts.get("GET_200_likely_automated", 0),
            "get_200_unknown_agent": event_counts.get("GET_200_unknown_agent", 0),
            "post_2xx_or_3xx_requests": sum(
                amount for k, amount in event_counts.items()
                if k.startswith("POST_2") or k.startswith("POST_3")
            ),
            "status_family_counts": dict(sorted(statuses[name].items())),
        }
    report["interpretation"] = (
        "Browser-like is a UA heuristic, NOT proof of a human. HTTP status proves "
        "an endpoint response, NOT an invoice, money receipt, service activation or sale. "
        "Counts are requests, NOT unique visitors or a linked funnel. Archived logs may "
        "be incomplete or overlap; do not add their counts to an authoritative visitor census."
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, choices=(1, 7, 30), default=7)
    args = parser.parse_args()
    print(json.dumps(summarize(days=args.days), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
