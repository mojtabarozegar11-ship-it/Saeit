#!/usr/bin/env python3
"""Read-only discovery of staging duplicate-card source and private login robots."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


HOME = Path('/home/zomorod2')


class Cards(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.a: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'a':
            data = dict(attrs)
            self.a = {'href': data.get('href') or '', 'class': data.get('class') or '', 'label': ''}

    def handle_data(self, text: str) -> None:
        if self.a is not None:
            self.a['label'] += text

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self.a is not None:
            self.a['label'] = re.sub(r'\s+', ' ', self.a['label']).strip()[:95]
            if self.a['label']:
                self.links.append(self.a)
            self.a = None


def probe_public(url: str) -> dict[str, object]:
    try:
        with urlopen(Request(url, headers={'User-Agent': 'ZM-Multisite-ReadOnly/1.0'}), timeout=25) as response:
            data = response.read(180000)
            html = data.decode('utf-8', 'replace')
            cards = Cards()
            cards.feed(html)
            grouped: dict[str, list[dict[str, str]]] = {}
            for link in cards.links:
                grouped.setdefault(link['label'], []).append(link)
            duplicates = {label: destinations for label, destinations in grouped.items()
                          if len(destinations) > 1 and len(label) > 3}
            return {'http': response.status, 'x_robots_tag': response.headers.get('X-Robots-Tag'),
                    'title': re.findall(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)[:1],
                    'total_links': len(cards.links), 'duplicate_link_labels': duplicates,
                    'h2_headings': [re.sub('<[^>]+>', '', x).strip()[:85] for x in
                                    re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)][:24],
                    'html_sha': hashlib.sha256(data).hexdigest()}
    except Exception as exc:
        return {'status': 'UNAVAILABLE', 'reason_type': type(exc).__name__}


def file_info(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 500000:
        return {'present_regular_bounded': False}
    content = path.read_bytes()
    text = content.decode('utf-8', 'replace')
    return {'present_regular_bounded': True, 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(),
            'has_x_robots_tag': bool(re.search(r'X-Robots-Tag', text, re.I)),
            'has_robots_meta': bool(re.search(r'<meta[^>]*name=[\"\']robots[\"\']', text, re.I)),
            'is_php': text.lstrip().startswith('<?php'),
            'contains_staging_title': 'خدمات و اکوسیستم یکپارچه' in text,
            'contains_management_title': 'میز مدیریت و حسابداری' in text}


def source_inventory() -> dict[str, object]:
    selected = {
        'staging_web_htaccess': HOME / 'Saeit-staging-web/.htaccess',
        'staging_wsgi': HOME / 'Saeit-staging/admin-smoke/passenger_wsgi.py',
        'staging_core_services': HOME / 'Saeit-staging/core/templates/core/services.html',
        'staging_core_home': HOME / 'Saeit-staging/core/templates/core/home.html',
        'staging_root_index': HOME / 'Saeit-staging-web/index.html',
        'business_public_index': HOME / 'public_html/business/index.php',
        'business_public_app': HOME / 'public_html/business/app.php',
        'business_public_htaccess': HOME / 'public_html/business/.htaccess',
        'business_private_app': HOME / '.private/zomorod-business/app.php',
        'business_staging_app': HOME / 'Saeit-staging/content/zomorod-business/app.php',
        'business_primary_app': HOME / 'Saeit/content/zomorod-business/app.php',
    }
    return {name: file_info(path) for name, path in selected.items()}


def staging_public_card_source() -> dict[str, object]:
    path = HOME / 'Saeit-staging/core/templates/core/services.html'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 12000:
        return {'status': 'SOURCE_UNAVAILABLE'}
    code = path.read_text('utf-8', 'replace')
    if re.search(r'(?i)(?:api[_-]?key|password|client[_-]?secret|private[_-]?key)', code):
        return {'status': 'SAFE_OUTPUT_GUARD'}
    articles = re.findall(r'<article\b[^>]*>[\s\S]*?</article>', code, re.I)
    cards = []
    for item in articles[:30]:
        title = re.search(r'<h2[^>]*>(.*?)</h2>', item, re.I | re.S)
        if title:
            cards.append({'title': re.sub('<[^>]+>', '', title.group(1)).strip(),
                          'source_snippet': item[:1250]})
    return {'status': 'READ', 'total_explicit_articles': len(articles), 'cards': cards}


if __name__ == '__main__':
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('CPANEL_IDENTITY_MISMATCH')
    print('STAGING_BUSINESS_SOURCE_READONLY=' + json.dumps({
        'changed_files': 0,
        'public': {
            'staging': probe_public('https://staging.zomorodmelal.ir/'),
            'business': probe_public('https://zomorodmelal.ir/business/'),
        }, 'source': source_inventory(), 'staging_card_source': staging_public_card_source()},
        ensure_ascii=False, sort_keys=True))
