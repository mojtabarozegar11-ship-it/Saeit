#!/usr/bin/env python3
"""One-time aggregate traffic inventory on the established cPanel SSH relay.

No customer records, raw access lines, IP addresses, user agents, or secrets leave
the cPanel host. This script never writes files or changes cPanel settings.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gzip
import json
import re
import subprocess


ROOT = Path('/home/zomorod2')
BASES = ('zomorodmelal.ir', 'mojplaywin.com')
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=30)
BOT = re.compile(r'bot|spider|crawl|monitor|uptime|headless|curl|wget|python-requests|postman|github-actions|go-http-client', re.I)
APACHE = re.compile(r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"(GET|POST|HEAD)\s+(\S+)\s+HTTP/[^\"]+"\s+(\d{3})\s+.*?"[^\"]*"\s+"([^\"]*)"')
VALID = re.compile(r'^[a-z0-9][a-z0-9.-]{2,252}$')


def report(key, data):
    print(key + '=' + json.dumps(data, sort_keys=True, ensure_ascii=False))


def domains():
    known = set(BASES)
    status = 'fallback_known_domains'
    try:
        proc = subprocess.run(['uapi', '--output=json', 'DomainInfo', 'list_domains'],
                              capture_output=True, timeout=18, check=False)
        if proc.returncode == 0 and len(proc.stdout) < 2000000:
            obj = json.loads(proc.stdout.decode('utf-8'))
            result = obj.get('result') or {}
            if result.get('status') in (1, True):
                data = result.get('data') or {}
                if isinstance(data, dict):
                    for field in ('main_domain', 'addon_domains', 'sub_domains', 'parked_domains'):
                        value = data.get(field, [])
                        values = value if isinstance(value, list) else [value]
                        for item in values:
                            if isinstance(item, str):
                                host = item.lower().strip('. ')
                                if VALID.fullmatch(host) and any(
                                    host == base or host.endswith('.' + base) for base in BASES
                                ):
                                    known.add(host)
                    status = 'cpanel_domaininfo'
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        pass
    return sorted(known), status


def awstats(hosts):
    folder = ROOT / 'tmp' / 'awstats'
    stats = []
    inspected = 0
    if folder.is_dir() and not folder.is_symlink():
        for path in sorted(folder.iterdir(), key=lambda p: p.name):
            match = re.fullmatch(r'awstats(\d{2})(\d{4})\.(.+)\.txt', path.name)
            if not match or path.is_symlink() or not path.is_file():
                continue
            month, year, host = match.groups()
            if host not in hosts or not (1 <= int(month) <= 12):
                continue
            if (int(year), int(month)) < (CUTOFF.year, CUTOFF.month):
                continue
            if path.stat().st_size > 16000000 or inspected >= 150:
                continue
            inspected += 1
            info = {'domain': host, 'month': year + '-' + month}
            inside = False
            try:
                with path.open('rt', encoding='utf-8', errors='replace') as stream:
                    for line in stream:
                        if line.startswith('BEGIN_GENERAL'):
                            inside = True
                            continue
                        if line.startswith('END_GENERAL'):
                            break
                        if inside:
                            parts = line.strip().split(' ', 1)
                            if len(parts) == 2 and parts[0] in (
                                'TotalVisits', 'TotalUnique', 'TotalPages', 'TotalHits',
                                'TotalBytes', 'FirstTime', 'LastTime', 'LastUpdate'
                            ) and re.fullmatch(r'[0-9]+', parts[1]):
                                info[parts[0]] = int(parts[1])
                if len(info) > 2:
                    stats.append(info)
            except OSError:
                continue
    report('MULTISITE_AWSTATS', {
        'source': 'cpanel_local_monthly_awstats', 'folder_available': folder.is_dir(),
        'files_inspected': inspected, 'records': stats,
        'note': 'Calendar-month totals as stored by AWStats; not additive to raw-log hits.'
    })


def log_host(filename, hosts):
    for host in sorted(hosts, key=len, reverse=True):
        for prefix in (host, 'www.' + host):
            if filename.startswith((prefix + '-', prefix + '_', prefix + '.')):
                return host
    return None


def is_page(path):
    return path == '/' or path.endswith(('/', '.html', '.htm', '.php'))


def raw_logs(hosts):
    folder = ROOT / 'logs'
    files = []
    skipped_oversize = 0
    if folder.is_dir() and not folder.is_symlink():
        for path in folder.iterdir():
            if not path.is_file() or path.is_symlink():
                continue
            host = log_host(path.name.lower(), hosts)
            if host is None or not path.name.lower().endswith(('.gz', '.log', '_log')):
                continue
            if path.stat().st_size > 120000000:
                skipped_oversize += 1
                continue
            files.append((host, path))
    files.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
    selected = files[:80]
    totals = defaultdict(lambda: {
        'files_scanned': 0, 'log_lines_scanned': 0, 'requests_30d': 0,
        'successful_page_requests': 0, 'likely_human_page_requests': 0,
        'likely_bot_page_requests': 0, 'store_page_requests': 0,
        'product_page_requests': 0, 'checkout_page_requests': 0,
        'http_4xx_page_requests': 0, 'http_5xx_page_requests': 0,
        'first_utc': None, 'last_utc': None,
    })
    unique = defaultdict(set)
    truncated = False
    scanned = 0
    for host, path in selected:
        row = totals[host]
        row['files_scanned'] += 1
        opener = gzip.open if path.name.lower().endswith('.gz') else open
        try:
            with opener(path, 'rt', encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    scanned += 1
                    row['log_lines_scanned'] += 1
                    if scanned > 1800000:
                        truncated = True
                        break
                    matched = APACHE.match(line)
                    if not matched:
                        continue
                    ip, timestamp, method, target, status, agent = matched.groups()
                    try:
                        at = datetime.strptime(timestamp, '%d/%b/%Y:%H:%M:%S %z').astimezone(timezone.utc)
                    except ValueError:
                        continue
                    if not CUTOFF <= at <= NOW + timedelta(minutes=5):
                        continue
                    row['requests_30d'] += 1
                    date = at.isoformat()
                    row['first_utc'] = min(row['first_utc'], date) if row['first_utc'] else date
                    row['last_utc'] = max(row['last_utc'], date) if row['last_utc'] else date
                    target = target.split('?', 1)[0]
                    if not is_page(target) or method != 'GET':
                        continue
                    if status.startswith('4'):
                        row['http_4xx_page_requests'] += 1
                    elif status.startswith('5'):
                        row['http_5xx_page_requests'] += 1
                    if not status.startswith(('2', '3')):
                        continue
                    row['successful_page_requests'] += 1
                    if BOT.search(agent):
                        row['likely_bot_page_requests'] += 1
                        continue
                    row['likely_human_page_requests'] += 1
                    if len(unique[host]) < 100000:
                        unique[host].add(ip)
                    if target.startswith('/store/'):
                        row['store_page_requests'] += 1
                    if target.startswith('/store/product/') and '/checkout/' not in target:
                        row['product_page_requests'] += 1
                    if '/checkout/' in target:
                        row['checkout_page_requests'] += 1
        except (OSError, EOFError, ValueError):
            row['file_read_errors'] = row.get('file_read_errors', 0) + 1
        if truncated:
            break
    for host, row in totals.items():
        row['approx_distinct_ips'] = len(unique[host])
    report('MULTISITE_RAW_LOGS', {
        'source': 'cpanel_raw_access_30d', 'generated_utc': NOW.isoformat(),
        'cutoff_utc': CUTOFF.isoformat(), 'available': folder.is_dir(),
        'files_available': len(files), 'files_scanned': len(selected),
        'skipped_oversize': skipped_oversize, 'truncated': truncated,
        'domain_rows': dict(sorted(totals.items())),
        'limitations': 'Request counts are not visits or humans; IP counts are approximations; archives can lag or overlap.'
    })


if __name__ == '__main__':
    hosts, source = domains()
    report('MULTISITE_DOMAINS', {'source': source, 'hosts': hosts, 'readonly': True})
    awstats(hosts)
    raw_logs(hosts)
    report('MULTISITE_AUDIT', {'completed': True, 'remote_writes': False,
                               'raw_identifiers_printed': False})
