#!/usr/bin/env python3
"""Read-only, bounded audit of public links/assets and form wiring."""
from __future__ import annotations

import concurrent.futures
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

SEEDS = {
    'zomorodmelal.ir': ('/', '/agriculture/', '/industry/', '/research/',
                         '/newsletter/', '/apps/', '/contact/'),
    'staging.zomorodmelal.ir': ('/',),
    'mojplaywin.com': ('/',),
}
EXCLUDED = re.compile(
    r'(?i)(?:^|/)(?:admin|staff|account|accounts|login|logout|signout|checkout|'
    r'cart|payments?|wallet|invoice|orders?|download|delete|remove|reset|'
    r'callback|webhook|api|cron|manage|private|debug|test|unsubscribe|'
    r'verify|token|factory)(?:/|$)'
)
SAFE_EXTENSIONS = {'.html', '.htm', '.php', '.css', '.js', '.png', '.jpg', '.jpeg',
                   '.svg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.pdf'}


class PublicReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.forms: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            self.links.append(('link', a['href'] or ''))
        elif tag == 'script' and a.get('src'):
            self.links.append(('script', a['src'] or ''))
        elif tag == 'link' and a.get('href') and 'stylesheet' in (a.get('rel') or '').lower():
            self.links.append(('css', a['href'] or ''))
        elif tag == 'img' and a.get('src'):
            self.links.append(('image', a['src'] or ''))
        elif tag == 'form':
            self.forms.append(((a.get('method') or 'GET').upper(), a.get('action') or ''))


def get(url: str) -> tuple[int, str, str, str]:
    req = Request(url, headers={'User-Agent': 'ZM-ReadOnly-Public-Link-Audit/1.0',
                                'Cache-Control': 'no-cache'})
    try:
        with urlopen(req, timeout=8) as res:
            body = res.read(80000)
            return (res.status, res.url, res.headers.get('Content-Type', '').split(';')[0].lower(),
                    body.decode('utf-8', 'replace') if 'text/html' in
                    res.headers.get('Content-Type', '').lower() else '')
    except HTTPError as exc:
        return (exc.code, exc.url, '', '')


def acceptable_url(seed: str, value: str) -> str | None:
    if value.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:', 'blob:', '//')):
        return None
    target = urljoin(seed, value)
    parsed = urlsplit(target)
    source_host = urlsplit(seed).hostname
    if (parsed.scheme != 'https' or parsed.hostname != source_host
            or not parsed.path.startswith('/') or len(parsed.path) > 165
            or len(parsed.path.split('/')) > 8 or EXCLUDED.search(parsed.path)):
        return None
    extension = '.' + parsed.path.rsplit('.', 1)[-1].lower() if '.' in parsed.path.rsplit('/', 1)[-1] else ''
    if extension and extension not in SAFE_EXTENSIONS:
        return None
    return urlunsplit(('https', parsed.netloc, parsed.path or '/', '', ''))


def scan() -> dict[str, object]:
    candidates: dict[str, tuple[str, str]] = {}
    seed_results = []
    forms = []
    count_by_kind = Counter()
    for host, pages in SEEDS.items():
        for path in pages:
            seed = 'https://' + host + path
            try:
                status, final, content_type, html = get(seed)
                if status != 200 or not html:
                    seed_results.append({'host': host, 'path': path, 'status': status,
                                         'html': bool(html)})
                    continue
                page = PublicReferences()
                page.feed(html)
                seed_results.append({'host': host, 'path': path, 'status': status,
                                     'anchors': len(page.links), 'forms': len(page.forms)})
                for method, action in page.forms:
                    destination = acceptable_url(seed, action or path)
                    forms.append({'origin': host + path, 'method': method,
                                  'safe_same_domain_action': destination is not None,
                                  'action_path': urlsplit(destination).path if destination else 'EXCLUDED_OR_EXTERNAL'})
                for kind, href in page.links:
                    candidate = acceptable_url(seed, href)
                    if not candidate:
                        continue
                    count_by_kind[kind] += 1
                    if candidate not in candidates:
                        candidates[candidate] = (host, kind)
            except (OSError, URLError, TimeoutError) as exc:
                seed_results.append({'host': host, 'path': path,
                                     'error_type': type(exc).__name__})

    # Cap requests for each host and resource type to avoid workload spikes.
    grouped: dict[str, dict[str, list[tuple[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for url, (host, kind) in sorted(candidates.items()):
        grouped[host][kind].append((url, kind))
    selected: list[tuple[str, str]] = []
    caps = {'link': 45, 'css': 22, 'script': 22, 'image': 30}
    for host in SEEDS:
        for kind, cap in caps.items():
            selected.extend(grouped[host][kind][:cap])

    def check(item: tuple[str, str]) -> dict[str, object]:
        url, kind = item
        try:
            status, final, content_type, html = get(url)
            result = {'host': urlsplit(url).hostname, 'path': urlsplit(url).path,
                      'kind': kind, 'status': status}
            if urlsplit(final).hostname != urlsplit(url).hostname:
                result['redirected_external'] = True
            if kind in ('css', 'script') and status == 200 and content_type.startswith('text/html'):
                result['html_instead_of_asset'] = True
            if kind == 'link' and status == 200 and html and re.search(
                    r'(?is)<title>\s*(?:404|not found|page not found)', html):
                result['possible_soft_404'] = True
            return result
        except (OSError, URLError, TimeoutError) as exc:
            return {'host': urlsplit(url).hostname, 'path': urlsplit(url).path,
                    'kind': kind, 'error_type': type(exc).__name__}

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(check, selected))
    broken = [x for x in results if x.get('status') not in (200,)
              or x.get('redirected_external') or x.get('html_instead_of_asset')
              or x.get('possible_soft_404')]
    return {'seed_pages': seed_results, 'discovered_distinct_candidates': len(candidates),
            'checked_links_and_assets': len(selected), 'by_kind': dict(count_by_kind),
            'broken_or_suspicious_count': len(broken), 'broken_or_suspicious': broken[:45],
            'public_forms_count': len(forms), 'public_form_actions': forms[:25],
            'writes': 0, 'forms_submitted': 0}


if __name__ == '__main__':
    if sys.argv[1:] != ['readonly']:
        raise SystemExit('USAGE: readonly')
    print('PUBLIC_LINK_ASSET_FORM_AUDIT=' + json.dumps(scan(), ensure_ascii=False,
                                                       sort_keys=True), flush=True)
