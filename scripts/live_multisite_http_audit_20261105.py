#!/usr/bin/env python3
"""Read-only HTTPS smoke and on-page checks for the owner's live websites."""

from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


ROUTES = {
    'zomorodmelal.ir': [
        '/', '/agriculture/', '/industry/', '/about/', '/contact/', '/knowledge/',
        '/research/', '/research/projects/', '/business/', '/store/', '/newsletter/',
        '/games/', '/apps/', '/economic-reports/', '/auction/', '/ai/',
        '/ask-master/index.php', '/robots.txt', '/sitemap.xml',
    ],
    'mojplaywin.com': [
        '/', '/store/', '/store/product/72/', '/store/product/225/',
        '/store/product/879/', '/commerce/trx-easy/',
        '/commerce/trx-easy/purchases/', '/commerce/book/72/',
        '/commerce/book/225/', '/studio/', '/company/', '/knowledge/',
        '/support/', '/privacy/', '/terms/', '/games/', '/contact/',
        '/robots.txt', '/sitemap.xml',
    ],
}
TEXT_TYPES = ('text/html', 'application/xhtml+xml')
USER_AGENT = 'ZomorodMelalReadOnlySiteAudit/20261105'


class MetaReader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.title = ''
        self.h1_count = 0
        self.description = False
        self.viewport = False
        self.canonical: str | None = None
        self.robots: str | None = None
        self.lang: str | None = None
        self.active_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if tag == 'html':
            self.lang = d.get('lang')
        elif tag == 'title':
            self.active_title = True
            self.title_count += 1
        elif tag == 'h1':
            self.h1_count += 1
        elif tag == 'meta':
            name = (d.get('name') or '').lower()
            if name == 'description':
                self.description = bool((d.get('content') or '').strip())
            elif name == 'viewport':
                self.viewport = True
            elif name == 'robots':
                self.robots = d.get('content')
        elif tag == 'link' and (d.get('rel') or '').lower() == 'canonical':
            self.canonical = d.get('href')

    def handle_endtag(self, tag: str) -> None:
        if tag == 'title':
            self.active_title = False

    def handle_data(self, data: str) -> None:
        if self.active_title and len(self.title) < 240:
            self.title += data


def allowed_host(host: str) -> bool:
    return host in ROUTES or host.endswith('.zomorodmelal.ir') or host.endswith('.mojplaywin.com')


def request(url: str) -> dict[str, object]:
    row: dict[str, object] = {'url': url}
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT,
                                                     'Cache-Control': 'no-cache',
                                                     'Cookie': ''})
        with urllib.request.urlopen(req, timeout=17) as response:
            row['http'] = response.status
            row['final_url'] = response.url
            row['content_type'] = response.headers.get_content_type()
            row['x_robots_tag'] = response.headers.get('X-Robots-Tag')
            row['hsts'] = bool(response.headers.get('Strict-Transport-Security'))
            row['bytes_read'] = len(body := response.read(250000))
            if not allowed_host((urllib.parse.urlsplit(response.url).hostname or '').lower()):
                row['external_redirect'] = True
                return row
            if response.headers.get_content_type() in TEXT_TYPES:
                parser = MetaReader()
                parser.feed(body.decode('utf-8', 'replace'))
                row.update(title=parser.title[:110], title_count=parser.title_count,
                           h1_count=parser.h1_count, description=parser.description,
                           viewport=parser.viewport, canonical=parser.canonical,
                           robots_meta=parser.robots, html_lang=parser.lang)
    except urllib.error.HTTPError as exc:
        row.update(http=exc.code, error='HTTP_' + str(exc.code))
    except Exception as exc:
        row['error'] = type(exc).__name__
    return row


def registered_subdomains(lines: list[str]) -> list[str]:
    found = set()
    for line in lines:
        prefix = 'LIVE_MULTISITE_CPANEL_INVENTORY='
        if prefix not in line:
            continue
        try:
            doc = json.loads(line.split(prefix, 1)[1])
            values = doc.get('domains', {}).get('domains', [])
            for host in values:
                if (isinstance(host, str) and allowed_host(host)
                        and host not in ROUTES and re.fullmatch(r'[a-z0-9.-]{5,160}', host)):
                    found.add(host)
        except (ValueError, TypeError, AttributeError):
            pass
    return sorted(found)[:35]


def main() -> None:
    inventory_lines = sys.stdin.read(150000).splitlines()
    hosts = registered_subdomains(inventory_lines)
    urls = [f'https://{host}{path}' for host, paths in ROUTES.items() for path in paths]
    urls.extend(f'https://{host}/' for host in hosts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=9) as pool:
        results = list(pool.map(request, urls))
    statuses: dict[str, int] = {}
    for result in results:
        code = str(result.get('http') or result.get('error') or 'UNKNOWN')
        statuses[code] = statuses.get(code, 0) + 1
        print('LIVE_MULTISITE_PAGE=' + json.dumps(result, ensure_ascii=False, sort_keys=True))
    print('LIVE_MULTISITE_SUMMARY=' + json.dumps({
        'count': len(results), 'discovered_subdomain_count': len(hosts),
        'discovered_subdomains': hosts, 'statuses': statuses,
        'read_only': True,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
