#!/usr/bin/env python3
"""Offline, read-only SKU-specific direct checkout CTA audit for S-01 snapshots.

No requests, credentials, orders, database or payment operations. This intentionally
ignores registration `next` query parameters: they are NOT direct checkout links.
"""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

DIRECT = re.compile(r'^/store/product/([1-9][0-9]*)/checkout/$')

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href', '').strip())

def audit(html, expected_sku, origin='https://mojplaywin.com'):
    if not re.fullmatch(r'[1-9][0-9]*', str(expected_sku)):
        raise ValueError('expected_sku must be a positive integer string')
    trusted = urlsplit(origin)
    if trusted.scheme != 'https' or not trusted.hostname or trusted.path not in ('', '/'):
        raise ValueError('origin must be an HTTPS site root')
    parser = Anchors()
    parser.feed(html)
    direct = []
    problems = []
    for href in parser.links:
        url = urlsplit(href)
        match = DIRECT.fullmatch(url.path)
        if not match:
            continue  # Registration next= is not a direct checkout CTA.
        if url.query or url.fragment:
            problems.append('direct_checkout_has_query_or_fragment')
            continue
        if url.netloc and (url.scheme != 'https' or url.netloc.lower() != trusted.netloc.lower()):
            problems.append('cross_origin_checkout')
            continue
        if url.scheme and url.scheme != 'https':
            problems.append('non_https_checkout')
            continue
        direct.append(match.group(1))
        if match.group(1) != str(expected_sku):
            problems.append('wrong_sku_direct_checkout')
    if str(expected_sku) not in direct:
        problems.append('expected_direct_checkout_missing')
    if len(direct) != 1:
        problems.append('direct_checkout_count_not_one')
    return {'sku': str(expected_sku), 'direct_checkout_count': len(direct),
            'issues': sorted(set(problems)), 'passed': not problems}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot', type=Path)
    ap.add_argument('--sku', required=True)
    ap.add_argument('--origin', default='https://mojplaywin.com')
    args = ap.parse_args()
    if not args.snapshot.is_file() or args.snapshot.suffix.lower() not in ('.html', '.htm'):
        ap.error('authorized local HTML snapshot required')
    result = audit(args.snapshot.read_text(encoding='utf-8'), args.sku, args.origin)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 2

if __name__ == '__main__':
    raise SystemExit(main())
