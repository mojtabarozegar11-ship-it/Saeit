#!/usr/bin/env python3
"""Privacy-preserving aggregate commercial path audit of cPanel web access logs.

Read a bounded tail of a small, fixed set of first-party log filenames. No IP,
user-agent, query, cookie, user/customer data or log line is emitted; there are
no writes, email events, purchases, or order mutations.
"""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import pwd
import re


DOMAIN = 'mojplaywin.com'
CANDIDATES = tuple(Path(p) for p in (
    '/home/zomorod2/access-logs/mojplaywin.com-ssl_log',
    '/home/zomorod2/access-logs/mojplaywin.com',
    '/home/zomorod2/logs/mojplaywin.com-ssl_log',
    '/home/zomorod2/logs/mojplaywin.com',
    '/usr/local/apache/domlogs/mojplaywin.com-ssl_log',
    '/usr/local/apache/domlogs/mojplaywin.com',
))
SAFE_ROOTS = ('/home/zomorod2/access-logs/', '/home/zomorod2/logs/',
              '/usr/local/apache/domlogs/')
MAX_TAIL = 3_000_000
REQUEST = re.compile(rb'"(GET|HEAD) (/[^? ]*)(?:\?[^ ]*)? HTTP/[0-9.]+" ([0-9]{3}) ')
STAMP = re.compile(rb'\[([0-9]{2}/[A-Za-z]{3}/[0-9]{4}:[0-9:]+) [+-][0-9]{4}\]')


def safe_file(path: Path) -> Path | None:
    if not path.exists() or not path.is_file():
        return None
    resolved = path.resolve()
    if not any(str(resolved).startswith(prefix) for prefix in SAFE_ROOTS):
        return None
    if resolved.name not in (DOMAIN, DOMAIN + '-ssl_log'):
        return None
    return resolved


def category(path: bytes) -> str | None:
    if path == b'/store/': return 'store_home'
    if re.fullmatch(rb'/store/product/[0-9]+/', path): return 'product_detail'
    if re.fullmatch(rb'/commerce/book/[0-9]+/', path): return 'checkout_view'
    if path == b'/commerce/trx-easy/': return 'trx_catalog'
    if path == b'/commerce/trx-easy/purchases/': return 'purchase_lookup'
    if path == b'/mpw-editorial/revenue/index.html': return 'revenue_hub'
    if path == b'/mpw-editorial/revenue/inquiry.php': return 'inquiry_form'
    if path == b'/ask-master/index.php': return 'ticket_form'
    return None


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Unexpected cPanel user')
    files = sorted(set(filter(None, (safe_file(p) for p in CANDIDATES))))
    if not files:
        print('MPW_ACCESSLOG_CANDIDATES_READABLE=0')
        print('MPW_ACCESSLOG_FURTHER_TRAFFIC_ANALYSIS=UNAVAILABLE')
        return
    counts: Counter[str] = Counter()
    first = last = None
    scanned = 0
    for file in files:
        with file.open('rb') as stream:
            size=file.stat().st_size
            if size > MAX_TAIL:
                stream.seek(size-MAX_TAIL)
                stream.readline()  # skip partial record
            for line in stream:
                scanned += 1
                if len(line) > 8192:
                    continue
                event=REQUEST.search(line)
                if not event or event.group(1)!=b'GET' or event.group(3)!=b'200':
                    continue
                cat=category(event.group(2))
                if cat is None:continue
                counts[cat]+=1
                time=STAMP.search(line)
                if time:
                    stamp=time.group(1).decode('ascii','replace')
                    if first is None:first=stamp
                    last=stamp
    print('MPW_ACCESSLOG_FILES_READABLE=' + str(len(files)))
    print('MPW_ACCESSLOG_LINES_SCANNED=' + str(scanned))
    print('MPW_ACCESSLOG_MATCHED_FIRST=' + (first or 'none'))
    print('MPW_ACCESSLOG_MATCHED_LAST=' + (last or 'none'))
    for name in ('store_home','product_detail','checkout_view','trx_catalog',
                 'purchase_lookup','revenue_hub','inquiry_form','ticket_form'):
        print('MPW_GET_200_' + name.upper() + '=' + str(counts[name]))
    print('MPW_ACCESSLOG_RAW_PERSONAL_DATA_EXPORTED=0')


if __name__ == '__main__':main()
