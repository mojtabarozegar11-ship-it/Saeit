#!/usr/bin/env python3
"""Aggregate existing MojPlayWin cPanel access logs without exposing visitors.

Only reads a bounded tail of the site's existing Apache/LiteSpeed log files.
No raw IP, user agent, URL query, invoice ID, email or log line is printed or
written. No HTTP requests, database connections, mail or payment operations.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import pwd
import re
import sys


ACCOUNT = Path("/home/zomorod2")
DOMAIN = "mojplaywin.com"
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_LINES = 600_000
LOOKBACK_DAYS = 7
MONTHS = {v: i for i, v in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
ACCESS_RE = re.compile(
    r'^\S+ \S+ \S+ \[(\d{2})/([A-Za-z]{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-]\d{4})\] '
    r'"(GET|POST|HEAD) ([^ "\t]+) HTTP/[0-9.]+" (\d{3})(?: |$)'
)
AUTOMATION_RE = re.compile(
    r'(bot|crawl|spider|curl/|wget/|python-|headless|lighthouse|pagespeed|'
    r'uptime|healthcheck|monitor|semrush|ahrefs|bingpreview|facebookexternalhit|'
    r'google-inspectiontool|yandeximages)', re.I
)
DETAIL_RE = re.compile(r'^/store/product/[1-9][0-9]*/?$')
CHECKOUT_RE = re.compile(r'^/commerce/book/[1-9][0-9]*/?$')
START_RE = re.compile(r'^/commerce/trx-easy/start/[1-9][0-9]*/?$')
INVOICE_RE = re.compile(r'^/commerce/trx-easy/invoice/[1-9][0-9]*/?$')
DOWNLOAD_RE = re.compile(r'^/commerce/trx-easy/download/[1-9][0-9]*/?$')


def _parse(line: str):
    match = ACCESS_RE.match(line)
    if not match:
        return None
    day, mon, year, hour, minute, second, offset, method, target, status = match.groups()
    if mon not in MONTHS:
        return None
    try:
        stamp = datetime(int(year), MONTHS[mon], int(day), int(hour), int(minute),
                         int(second), tzinfo=timezone(timedelta(
                             hours=int(offset[:3]), minutes=int(offset[0] + offset[3:]))))
    except ValueError:
        return None
    # Discard query strings, which can contain secrets or identifiers.
    path = target.split('?', 1)[0].split('#', 1)[0]
    if not path.startswith('/'):
        return None
    user_agent = line.rsplit('"', 2)[-2] if line.count('"') >= 6 else ''
    automated = bool(AUTOMATION_RE.search(user_agent))
    return stamp.astimezone(timezone.utc), method, path, int(status), automated


def _category(method, path):
    if method == 'GET' and path in ('/store/', '/store'):
        return 'store_get'
    if method == 'GET' and DETAIL_RE.fullmatch(path):
        return 'product_detail_get'
    if method == 'GET' and (CHECKOUT_RE.fullmatch(path) or
                            path.rstrip('/') == '/commerce/trx-easy'):
        return 'checkout_get'
    if method == 'POST' and START_RE.fullmatch(path):
        return 'order_post'
    if method == 'GET' and INVOICE_RE.fullmatch(path):
        return 'invoice_get'
    if method == 'GET' and DOWNLOAD_RE.fullmatch(path):
        return 'download_get'
    return None


def _logs():
    candidates = []
    for folder in (ACCOUNT / 'access-logs', Path('/usr/local/apache/domlogs')):
        if not folder.is_dir():
            continue
        try:
            children = list(folder.iterdir())[:500]
        except OSError:
            continue
        for entry in children:
            name = entry.name.lower()
            if not (name == DOMAIN or name.startswith(DOMAIN + '-') or
                    name == 'www.' + DOMAIN or name.startswith('www.' + DOMAIN + '-')):
                continue
            if name.endswith(('.gz', '.zip', '.tar', '.bz2', '.xz')):
                continue
            try:
                target = entry.resolve(strict=True)
                if (not target.is_file() or not
                        (target.is_relative_to(ACCOUNT) or
                         target.is_relative_to(Path('/usr/local/apache/domlogs')))):
                    continue
                info = target.stat()
            except (OSError, RuntimeError):
                continue
            if info.st_size > 0:
                candidates.append((info.st_dev, info.st_ino, target, info.st_size))
    dedup = {}
    for device, inode, target, size in candidates:
        dedup[(device, inode)] = (target, size)
    return list(dedup.values())


def _audit():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    totals = Counter()
    day_counts = defaultdict(Counter)
    source_files = _logs()
    truncated = False
    scanned_lines = 0
    for path, size in source_files:
        try:
            with path.open('rb') as stream:
                if size > MAX_LOG_BYTES:
                    stream.seek(-MAX_LOG_BYTES, os.SEEK_END)
                    stream.readline()  # discard incomplete first line
                    truncated = True
                for raw in stream:
                    scanned_lines += 1
                    if scanned_lines > MAX_LINES:
                        truncated = True
                        break
                    parsed = _parse(raw.decode('utf-8', 'replace'))
                    if parsed is None:
                        continue
                    stamp, method, req_path, code, automated = parsed
                    if not cutoff <= stamp <= now:
                        continue
                    stage = _category(method, req_path)
                    if stage is None:
                        continue
                    group = 'suspected_bot' if automated else 'unclassified_browser'
                    status_class = str(code // 100) + 'xx'
                    key = group + ':' + stage + ':' + status_class
                    totals[key] += 1
                    day_counts[stamp.date().isoformat()][key] += 1
                if scanned_lines > MAX_LINES:
                    break
        except (OSError, PermissionError):
            totals['unreadable_log_files'] += 1
    return {
        'status': 'aggregated' if source_files else 'logs_unavailable',
        'utc_window_end': now.date().isoformat(),
        'days': LOOKBACK_DAYS,
        'files_accessible': len(source_files),
        'tail_limited': truncated,
        'scanned_lines': min(scanned_lines, MAX_LINES),
        'totals': dict(sorted(totals.items())),
        'daily': {day: dict(sorted(values.items()))
                  for day, values in sorted(day_counts.items())},
        'uniques_unavailable': True,
        'bot_classification': 'heuristic_only',
        'orders_are_not_payments': True,
        'read_only': True,
        'emails': 0,
        'payments': 0,
        'database_writes': 0,
    }


def _selftest():
    fixture = ('127.0.0.1 - - [06/Nov/2026:09:13:15 +0330] '
               '"GET /store/?token=do-not-print HTTP/2.0" 200 123 '
               '"-" "Mozilla/5.0"')
    parsed = _parse(fixture)
    assert parsed is not None
    assert parsed[0].hour == 5 and parsed[0].minute == 43
    assert parsed[2] == '/store/' and parsed[3] == 200 and not parsed[4]
    assert _category('GET', parsed[2]) == 'store_get'
    assert _category('POST', '/commerce/trx-easy/start/72/') == 'order_post'
    assert _category('GET', '/commerce/trx-easy/invoice/12/') == 'invoice_get'
    assert _category('GET', '/admin/') is None
    print('MPW_ACCESS_FUNNEL_SELFTEST=PASS')


def main():
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest':
        _selftest()
        return
    if len(sys.argv) != 1 or pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('WRONG_HOST_OR_ARGUMENTS')
    print('MPW_ACCESS_FUNNEL=' + json.dumps(_audit(), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
