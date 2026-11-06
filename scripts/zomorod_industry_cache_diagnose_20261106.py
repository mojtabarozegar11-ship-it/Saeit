#!/usr/bin/env python3
"""Read-only cache diagnosis for one published static Zomorod industry page.

No secret, key, customer data, full .htaccess file or authentication material is printed.
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

PAGE = Path('/home/zomorod2/public_html/industry/index.html')
ROOT = Path('/home/zomorod2/public_html')
MARKER = 'zm-production-oee-20261106:page'
PATH = 'https://zomorodmelal.ir/industry/'
SAFE_HEADERS = ('cache-control', 'pragma', 'expires', 'age', 'etag', 'last-modified', 'x-litespeed-cache', 'x-litespeed-cache-control', 'x-qc-cache', 'cf-cache-status', 'vary', 'server')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:20]


def public():
    for label, url, request_headers in [
        ('plain-default', PATH, {'User-Agent': 'Mozilla/5.0 ZomorodIndustryCacheAudit/1.0'}),
        ('plain-no-cache', PATH, {'User-Agent': 'Mozilla/5.0 ZomorodIndustryCacheAudit/1.0', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}),
        ('query-bust', PATH + '?cache_audit=20261106_68', {'User-Agent': 'Mozilla/5.0 ZomorodIndustryCacheAudit/1.0'})
    ]:
        request = Request(url, headers=request_headers)
        with urlopen(request, timeout=30) as response:
            body = response.read(1100000).decode('utf-8', 'replace')
            headers = {k: response.headers.get(k) for k in SAFE_HEADERS if response.headers.get(k)}
            result = {'case': label, 'status': response.status, 'len': len(body), 'digest': digest(body), 'has_oee_action': MARKER in body, 'headers': headers}
        print('PUBLIC_CACHE_SAMPLE=' + json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)


def origin():
    if not PAGE.is_file():
        raise RuntimeError('ORIGIN_INDUSTRY_PAGE_MISSING')
    data = PAGE.read_text(encoding='utf-8')
    print('ORIGIN_PAGE=' + json.dumps({'digest': digest(data), 'len': len(data), 'has_oee_action': MARKER in data}, sort_keys=True), flush=True)
    for directory in [ROOT, ROOT / 'industry', ROOT / 'topics']:
        file = directory / '.htaccess'
        if not file.is_file():
            print('ORIGIN_CACHE_CONF=' + json.dumps({'location': str(directory.relative_to(ROOT)), 'exists': False}), flush=True)
            continue
        content = file.read_text(encoding='utf-8', errors='replace')
        findings = {
            'location': str(directory.relative_to(ROOT)),
            'exists': True,
            'expires_html': re.findall(r'(?im)^\s*ExpiresByType\s+text/html\s+([^\s#]+)', content),
            'expires_default': re.findall(r'(?im)^\s*ExpiresDefault\s+([^\s#]+)', content),
            'header_cache_control_present': bool(re.search(r'(?im)^\s*Header\s+(?:always\s+)?(?:set|append|merge)\s+Cache-Control\b', content)),
            'cache_enable_present': bool(re.search(r'(?im)^\s*CacheEnable\b', content)),
            'cache_lookup_present': bool(re.search(r'(?im)^\s*CacheLookup\b', content)),
            'litespeed_cache_env_present': 'cache-control:' in content.lower(),
            'rewrite_rules_count': len(re.findall(r'(?im)^\s*RewriteRule\b', content)),
            'passenger_static_off': 'PassengerEnabled off' in content,
        }
        print('ORIGIN_CACHE_CONF=' + json.dumps(findings, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['public']:
        public()
    elif sys.argv[1:] == ['origin']:
        origin()
    else:
        raise RuntimeError('MODE_MUST_BE_PUBLIC_OR_ORIGIN')
