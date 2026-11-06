#!/usr/bin/env python3
"""Aggregate existing MojPlayWin cPanel access logs without exposing visitors.

Only reads a bounded tail of the site's existing Apache/LiteSpeed log files.
No raw IP, user agent, URL query, invoice ID, email or log line is printed or
written. A small, separately bounded Passenger stderr probe reports only
exception class counts. No HTTP requests, database connections, mail or
payment operations.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import gzip
from io import BytesIO
import json
import os
from pathlib import Path
import pwd
import re
import sys


ACCOUNT = Path("/home/zomorod2")
DOMAIN = "mojplaywin.com"
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_COMPRESSED_BYTES = 16 * 1024 * 1024
MAX_LINES = 600_000
MAX_STDERR_BYTES = 1024 * 1024
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
AWSTATS_RE = re.compile(r'^awstats(0[1-9]|1[0-2])(20[0-9]{2})\.(?:www\.)?mojplaywin\.com\.txt$')
EXCEPTION_RE = re.compile(
    r'^(?:[A-Za-z_]\w*\.)*'
    r'(OperationalError|IntegrityError|ProgrammingError|DatabaseError|'
    r'DataError|InterfaceError|InternalError|ValueError|TypeError|'
    r'AttributeError|KeyError|RuntimeError|ImportError|ModuleNotFoundError|'
    r'PaymentHold|ValidationError|AssertionError|PermissionError|'
    r'TimeoutError|ConnectionError|OSError):')
TARGET_ERROR_ROUTE = '/commerce/trx-easy/start/779/'
FRAME_RE = re.compile(
    r'^\s*File "/home/zomorod2/(?:Saeit-staging|mojplaywin\.com)/'
    r'((?:config|services|core|mpw_commerce|scripts)/'
    r'[A-Za-z_][A-Za-z0-9_./-]*\.py)", line ([1-9][0-9]{0,5}), '
    r'in ([A-Za-z_][A-Za-z0-9_]*)')
MISSING_IMPORT_RE = re.compile(
    r"^ModuleNotFoundError: No module named '([A-Za-z_][A-Za-z0-9_.]{0,100})'$")


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


def _public_error_bucket(stamp, stage, path, code, automated):
    """Categorize server errors without retaining visitor or invoice identifiers."""
    if code < 500 or stage not in ('checkout_get', 'order_post'):
        return None
    matched = (CHECKOUT_RE.fullmatch(path) if stage == 'checkout_get'
               else START_RE.fullmatch(path))
    if stage == 'order_post' and matched is None:
        return None
    public_product = int(path.rstrip('/').rsplit('/', 1)[-1]) if matched else 0
    return (stamp.date().isoformat(), stage, code, public_product,
            'suspected_bot' if automated else 'unclassified_browser')


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


def _archives():
    """Read archived cPanel Raw Access logs as a fallback, without extracting.

    cPanel can place monthly .gz archives in /home/USERNAME/logs. Never copy or
    print their contents. Only account-owned regular files under that folder
    are eligible, and decompression is bounded separately in _audit().
    """
    folder = ACCOUNT / 'logs'
    if folder.is_symlink() or not folder.is_dir():
        return []
    try:
        children = sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime,
                          reverse=True)[:300]
    except OSError:
        return []
    result = []
    for entry in children:
        name = entry.name.lower()
        if (not name.endswith('.gz') or
                not (name.startswith(DOMAIN + '-') or
                     name.startswith(DOMAIN + '.') or
                     name.startswith('www.' + DOMAIN + '-') or
                     name.startswith('www.' + DOMAIN + '.'))):
            continue
        try:
            if entry.is_symlink():
                continue
            actual = entry.resolve(strict=True)
            if not actual.is_relative_to(folder.resolve()) or not actual.is_file():
                continue
            info = actual.stat()
            if (info.st_uid != os.geteuid() or info.st_nlink != 1 or
                    not 0 < info.st_size <= MAX_ARCHIVE_COMPRESSED_BYTES):
                continue
        except (OSError, RuntimeError):
            continue
        result.append((actual, info.st_size))
        if len(result) >= 4:
            break
    return result


def _awstats_monthly():
    """Read only AWStats' aggregate GENERAL block, never visit/IP sections."""
    folder = ACCOUNT / 'tmp/awstats'
    if not folder.is_dir():
        return {'available': False, 'monthly': []}
    reports = []
    try:
        paths = sorted(folder.iterdir(), key=lambda entry: entry.name, reverse=True)
    except OSError:
        return {'available': False, 'monthly': []}
    for path in paths[:350]:
        match = AWSTATS_RE.fullmatch(path.name)
        if match is None:
            continue
        try:
            actual = path.resolve(strict=True)
            if not actual.is_file() or not actual.is_relative_to(ACCOUNT):
                continue
            month = match.group(2) + '-' + match.group(1)
            values = {}
            in_general = False
            with actual.open('rb') as stream:
                # General is at the head of AWStats files; never scan raw visitor sections.
                for raw in stream.read(65_536).splitlines():
                    line = raw.decode('ascii', 'replace').strip()
                    if line.startswith('BEGIN_GENERAL'):
                        in_general = True
                        continue
                    if in_general and line.startswith('END_GENERAL'):
                        break
                    if not in_general:
                        continue
                    parts = line.split(maxsplit=1)
                    if len(parts) != 2 or parts[0] not in (
                            'LastUpdate', 'TotalVisits', 'TotalUnique',
                            'TotalPages', 'TotalHits'):
                        continue
                    if parts[1].isdecimal() and len(parts[1]) <= 18:
                        values[parts[0]] = int(parts[1])
            if all(key in values for key in ('TotalVisits', 'TotalPages', 'TotalHits')):
                reports.append({'month': month,
                                'source': 'www' if '.www.mojplaywin.com.' in path.name
                                else 'apex', 'general': values})
        except (OSError, RuntimeError):
            continue
        if len(reports) >= 6:
            break
    return {'available': bool(reports), 'monthly': reports}


def _stderr_counts(lines):
    """Read text internally; expose no message, request data or traceback."""
    counts = Counter()
    target_counts = Counter()
    target_mentions = 0
    window = -1
    last_app_frame = None
    code_frames = Counter()
    missing_imports = Counter()
    for index, raw in enumerate(lines):
        # Do not retain or include the original line in any output.
        line = raw.strip()
        if line.startswith('Traceback (most recent call last):'):
            last_app_frame = None
        match_frame = FRAME_RE.match(raw)
        if match_frame:
            path, line_number, function = match_frame.groups()
            if '..' not in path and len(path) <= 125:
                last_app_frame = (path, int(line_number), function)
        if TARGET_ERROR_ROUTE in line:
            target_mentions += 1
            window = index + 200
        found = EXCEPTION_RE.match(line)
        if found:
            category = found.group(1)
            counts[category] += 1
            if last_app_frame is not None:
                code_frames[(category, *last_app_frame)] += 1
            missing = MISSING_IMPORT_RE.fullmatch(line)
            if missing:
                missing_imports[missing.group(1)] += 1
            if index <= window:
                target_counts[category] += 1
    return {'exception_classes': dict(sorted(counts.items())),
            'target_order_route_mentions': target_mentions,
            'exception_classes_near_target': dict(sorted(target_counts.items())),
            'top_app_frames': [
                {'exception': exception, 'module': module, 'line': line_number,
                 'function': function, 'occurrences': count}
                for (exception, module, line_number, function), count
                in code_frames.most_common(12)
            ],
            'missing_import_modules': dict(missing_imports.most_common(10))}


def _passenger_stderr_probe():
    """Check cPanel's documented Python stderr.log, with bounded private reads."""
    locations = (
        ('staging_app', ACCOUNT / 'Saeit-staging/stderr.log'),
        ('public_app', ACCOUNT / 'mojplaywin.com/stderr.log'),
    )
    found = {}
    for label, path in locations:
        try:
            if path.is_symlink() or not path.is_file():
                continue
            actual = path.resolve(strict=True)
            if not actual.is_relative_to(ACCOUNT):
                continue
            stat = actual.stat()
            if stat.st_uid != os.geteuid() or stat.st_nlink != 1:
                continue
            with actual.open('rb') as stream:
                if stat.st_size > MAX_STDERR_BYTES:
                    stream.seek(-MAX_STDERR_BYTES, os.SEEK_END)
                    stream.readline()  # discard any incomplete first line
                contents = stream.read(MAX_STDERR_BYTES)
            observations = _stderr_counts(contents.decode('utf-8', 'replace').splitlines())
            found[label] = dict(observations,
                                scanned_bytes=len(contents),
                                tail_limited=stat.st_size > MAX_STDERR_BYTES,
                                modified_utc_day=datetime.fromtimestamp(
                                    stat.st_mtime, timezone.utc).date().isoformat())
        except (OSError, ValueError, RuntimeError):
            continue
    return {'available': bool(found), 'files': found,
            'raw_lines_disclosed': 0, 'read_only': True}


def _module_inventory():
    """Check the static existence of the module missing in Passenger tracebacks."""
    rows = {}
    for label, root in (('staging_app', ACCOUNT / 'Saeit-staging'),
                        ('public_app', ACCOUNT / 'mojplaywin.com')):
        module = root / 'core/zomorod_public_views.py'
        urls = root / 'config/urls.py'
        def safe_content(path):
            if path.is_symlink() or not path.is_file():
                return None
            actual = path.resolve(strict=True)
            if not actual.is_relative_to(root):
                return None
            stat = actual.stat()
            if stat.st_uid != os.geteuid() or not 0 < stat.st_size <= 128_000:
                return None
            return actual.read_bytes()
        try:
            module_data = safe_content(module)
            urls_data = safe_content(urls)
            rows[label] = {
                'missing_module_file_present': module_data is not None,
                'urls_file_present': urls_data is not None,
                'urls_import_reference': (b'core.zomorod_public_views' in urls_data
                                          if urls_data is not None else None),
            }
        except (OSError, RuntimeError, ValueError):
            rows[label] = {'probe_unavailable': True}
    return {'files': rows, 'read_only': True}


def _commerce_handler_structure():
    """Review live handler structure without showing source or configuration data."""
    root = ACCOUNT / 'Saeit-staging'
    targets = (
        ('commercial_web', 'services/mpw_trx_commercial_web.py',
         ('_start_order', '_configured_receiver')),
        ('commercial_intent', 'services/mpw_walletless_commercial_intent.py',
         ('_commercial_db',)),
        ('buyer_orders', 'mpw_commerce/buyer_orders.py', ('_eligible',)),
    )
    result = {}
    for label, rel, wanted in targets:
        p = root / rel
        try:
            if p.is_symlink() or not p.is_file():
                result[label] = {'present': False}
                continue
            actual = p.resolve(strict=True)
            info = actual.stat()
            if (not actual.is_relative_to(root) or info.st_uid != os.geteuid()
                    or not 0 < info.st_size <= 180_000):
                result[label] = {'safe_read_unavailable': True}
                continue
            parsed = ast.parse(actual.read_text('utf-8'))
            handlers = {}
            for node in parsed.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name not in wanted:
                    continue
                calls = set()
                handled = set()
                for descendant in ast.walk(node):
                    if isinstance(descendant, ast.Call):
                        name = (descendant.func.id if isinstance(descendant.func, ast.Name)
                                else descendant.func.attr if isinstance(descendant.func, ast.Attribute)
                                else None)
                        if name and name.isidentifier():
                            calls.add(name)
                    elif isinstance(descendant, ast.ExceptHandler) and descendant.type is not None:
                        exc = descendant.type
                        if isinstance(exc, ast.Name):
                            handled.add(exc.id)
                        elif isinstance(exc, ast.Attribute):
                            handled.add(exc.attr)
                handlers[node.name] = {'first_line': node.lineno,
                                       'last_line': node.end_lineno,
                                       'calls': sorted(calls)[:45],
                                       'caught_exceptions': sorted(handled)[:20]}
            result[label] = {'present': True, 'syntax_valid': True,
                             'handlers': handlers}
        except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError):
            result[label] = {'safe_inspection_unavailable': True}
    return {'read_only': True, 'raw_source_disclosed': False, 'files': result}


def _audit():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    totals = Counter()
    day_counts = defaultdict(Counter)
    server_errors = Counter()
    raw_files = _logs()
    archived_files = _archives() if not raw_files else []
    source_files = raw_files or archived_files
    archived = bool(archived_files)
    truncated = False
    scanned_lines = 0
    scanned_bytes = 0
    for path, size in source_files:
        try:
            opener = gzip.open if archived else Path.open
            with opener(path, 'rb') as stream:
                if not archived and size > MAX_LOG_BYTES:
                    stream.seek(-MAX_LOG_BYTES, os.SEEK_END)
                    stream.readline()  # discard incomplete first line
                    truncated = True
                for raw in stream:
                    scanned_lines += 1
                    scanned_bytes += len(raw)
                    if scanned_lines > MAX_LINES or scanned_bytes > MAX_LOG_BYTES:
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
                    error_bucket = _public_error_bucket(
                        stamp, stage, req_path, code, automated)
                    if error_bucket:
                        server_errors[error_bucket] += 1
                if scanned_lines > MAX_LINES:
                    break
        except (OSError, PermissionError, EOFError):
            totals['unreadable_log_files'] += 1
    return {
        'status': 'aggregated' if source_files else 'logs_unavailable',
        'utc_window_end': now.date().isoformat(),
        'days': LOOKBACK_DAYS,
        'files_accessible': len(source_files),
        'archive_files_accessible': len(archived_files),
        'source_kind': 'cPanel_raw_access_archives' if archived else
                       ('current_access_logs' if raw_files else 'none'),
        'tail_limited': truncated,
        'scanned_lines': min(scanned_lines, MAX_LINES),
        'scanned_bytes': min(scanned_bytes, MAX_LOG_BYTES),
        'totals': dict(sorted(totals.items())),
        'server_errors': [
            {'utc_day': day, 'stage': stage, 'http_status': status,
             'public_product_id': product_id, 'agent_class': agent_class,
             'requests': count}
            for (day, stage, status, product_id, agent_class), count
            in sorted(server_errors.items())
        ],
        'daily': {day: dict(sorted(values.items()))
                  for day, values in sorted(day_counts.items())},
        'awstats': _awstats_monthly(),
        'passenger_stderr': _passenger_stderr_probe(),
        'module_inventory': _module_inventory(),
        'commercial_handler_structure': _commerce_handler_structure(),
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
    with gzip.open(BytesIO(gzip.compress((fixture + '\n').encode('utf-8'))), 'rb') as stream:
        restored = stream.readline().decode('utf-8').strip()
    assert _parse(restored) == parsed
    assert _category('POST', '/commerce/trx-easy/start/72/') == 'order_post'
    assert _category('GET', '/commerce/trx-easy/invoice/12/') == 'invoice_get'
    assert _category('GET', '/admin/') is None
    assert _public_error_bucket(parsed[0], 'order_post',
                                '/commerce/trx-easy/start/72/?token=hidden', 500,
                                False) is None
    assert _public_error_bucket(parsed[0], 'order_post',
                                '/commerce/trx-easy/start/72/', 500, False)[3] == 72
    assert _public_error_bucket(parsed[0], 'invoice_get',
                                '/commerce/trx-easy/invoice/800/', 500, False) is None
    assert AWSTATS_RE.fullmatch('awstats112026.mojplaywin.com.txt')
    assert not AWSTATS_RE.fullmatch('awstats112026.other-site.com.txt')
    probe = _stderr_counts([
        'Internal Server Error: /commerce/trx-easy/start/779/',
        'Traceback (most recent call last):',
        'django.db.utils.OperationalError: sensitive text must never surface',
    ])
    assert probe['target_order_route_mentions'] == 1
    assert probe['exception_classes_near_target'] == {'OperationalError': 1}
    assert 'sensitive' not in repr(probe)
    sample = _stderr_counts([
        'Traceback (most recent call last):',
        '  File "/home/zomorod2/mojplaywin.com/services/checkout.py", '
        'line 42, in start',
        "ModuleNotFoundError: No module named 'safe_module'",
    ])
    assert sample['top_app_frames'][0]['module'] == 'services/checkout.py'
    assert sample['missing_import_modules'] == {'safe_module': 1}
    assert isinstance(_commerce_handler_structure(), dict)
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
