#!/usr/bin/env python3
"""Read-only, bounded live-site stability and destination inspection."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
HTACCESS = HOME / 'Saeit-staging-web/.htaccess'
TEMPLATE = APP / 'core/templates/core/services.html'
BRAND = APP / 'core/brand.py'
EXPECTED_TEMPLATE_HASH = 'e0de859b639bc56f7b3c58ccefdfd8c8dff2e5a18cf987837aa83a51ad200622'
EXPECTED_HTML_HASH = 'fade013a4a9f71d337bb4e5bec4cfff5b16e1c6f26c2119243780b84a9bc8355'
DESTINATIONS = {
    'پژوهش‌های کاربردی': '/research/projects/',
    'ابزارهای کاربردی': '/apps/',
    'خبرنامهٔ شرکت': '/newsletter/',
    'ارتباط و همکاری': '/contact/',
}
CORE_ROUTES = (
    '/', '/agriculture/', '/industry/', '/about/', '/contact/',
    '/knowledge/', '/research/', '/research/projects/', '/newsletter/',
    '/apps/', '/business/', '/games/', '/economic-reports/', '/auction/',
    '/ai/',
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, timeout: int = 10) -> tuple[int, bytes, dict[str, str], str]:
    request = Request(url, headers={
        'User-Agent': 'ZomorodMelal-Official-Readonly-Site-Audit/1.0',
        'Cache-Control': 'no-cache, no-store', 'Pragma': 'no-cache',
        'Connection': 'close',
    })
    try:
        with urlopen(request, timeout=timeout) as response:
            return (response.status, response.read(180000),
                    {k.lower(): v for k, v in response.headers.items()}, response.url)
    except HTTPError as exc:
        return (exc.code, b'', {}, exc.url)


def headings(html: str) -> list[str]:
    return [re.sub('<[^>]+>', '', x).strip() for x in
            re.findall(r'<h2\b[^>]*>(.*?)</h2>', html, re.I | re.S)]


def files_and_mapping() -> dict[str, object]:
    if any(not p.is_file() or p.is_symlink() for p in (HTACCESS, TEMPLATE, BRAND)):
        raise RuntimeError('STAGING_CANONICAL_SOURCE_MISSING_OR_SYMLINKED')
    conf = HTACCESS.read_text('utf-8', 'replace')
    roots = re.findall(r'(?m)^PassengerAppRoot\s+([^\r\n]+)$', conf)
    template = TEMPLATE.read_bytes()
    brand = BRAND.read_text('utf-8', 'replace')
    return {
        'passenger_app_root_exact': roots == [str(APP)],
        'canonical_services_sha_matches_release': sha(template) == EXPECTED_TEMPLATE_HASH,
        'stage_mpw_brand_fallback_removed': '"staging.zomorodmelal.ir": Brand(' not in brand,
        'main_app_root_unchanged': 'PassengerAppRoot "' + str(HOME / 'Saeit') + '"'
            in (HOME / 'public_html/.htaccess').read_text('utf-8', 'replace'),
        'mpw_app_root_unchanged': 'PassengerAppRoot ' + str(HOME / 'mojplaywin.com')
            in (HOME / 'mojplaywin.com/.htaccess').read_text('utf-8', 'replace'),
    }


def staging_public() -> dict[str, object]:
    signatures = []
    noindex = []
    problems = []
    for index in range(20):
        suffix = '?zm_post_release_' + str(index) + '=' + str(time.time_ns())
        try:
            status, body, headers, final = fetch('https://staging.zomorodmelal.ir/' + suffix)
            html = body.decode('utf-8', 'replace')
            h2s = headings(html)
            valid = (status == 200 and urlsplit(final).hostname == 'staging.zomorodmelal.ir'
                     and h2s.count('آموزش') == 1 and h2s.count('هوش مصنوعی') == 1
                     and all(h2s.count(title) == 1 for title in DESTINATIONS)
                     and all('https://zomorodmelal.ir' + target in html
                             for target in DESTINATIONS.values()))
            signatures.append(sha(body))
            noindex.append('noindex' in headers.get('x-robots-tag', '').lower())
            if not valid:
                problems.append({'request': index, 'status': status, 'headings': len(h2s)})
        except (OSError, URLError, TimeoutError) as exc:
            problems.append({'request': index, 'error_type': type(exc).__name__})
    return {
        'requests': 20,
        'complete_card_and_link_match': len(signatures) == 20 and not problems,
        'all_pages_same_sha': len(set(signatures)) == 1 and len(signatures) == 20,
        'matches_original_release_sha': set(signatures) == {EXPECTED_HTML_HASH},
        'all_responses_noindex': len(noindex) == 20 and all(noindex),
        'observed_html_sha': signatures[0] if len(signatures) == 20 and len(set(signatures)) == 1 else 'NON_UNIFORM',
        'problems': problems[:12],
    }


def public_routes() -> list[dict[str, object]]:
    report = []
    for path in CORE_ROUTES:
        try:
            status, _data, _headers, final = fetch('https://zomorodmelal.ir' + path)
            same_domain = urlsplit(final).hostname in ('zomorodmelal.ir', 'www.zomorodmelal.ir')
            report.append({'path': path, 'status': status,
                           'same_domain': same_domain,
                           'final_path': urlsplit(final).path if same_domain else 'OTHER_DOMAIN'})
        except (OSError, URLError, TimeoutError) as exc:
            report.append({'path': path, 'error_type': type(exc).__name__})
    try:
        status, body, _, final = fetch('https://mojplaywin.com/')
        report.append({'path': 'mojplaywin.com/', 'status': status,
                       'same_domain': urlsplit(final).hostname in ('mojplaywin.com', 'www.mojplaywin.com'),
                       'title_preserved': b'Moj Play Win' in body})
    except (OSError, URLError, TimeoutError) as exc:
        report.append({'path': 'mojplaywin.com/', 'error_type': type(exc).__name__})
    return report


def main() -> None:
    if sys.argv[1:] != ['readonly']:
        raise SystemExit('USAGE: readonly')
    evidence = {'disk': files_and_mapping(), 'staging': staging_public(),
                'live_primary_destinations': public_routes(), 'writes': 0}
    print('POST_STAGE_ROOT_RELEASE_READONLY=' + json.dumps(evidence, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
