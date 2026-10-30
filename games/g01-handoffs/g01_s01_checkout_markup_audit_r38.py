#!/usr/bin/env python3
"""Offline, read-only accessibility gate for approved storefront HTML snapshots."""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.controls = []
        self.labels = set()
        self.ids = set()
        self.current = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get('id'):
            self.ids.add(a['id'])
        if tag == 'label' and a.get('for'):
            self.labels.add(a['for'])
        if tag == 'a':
            self.current = {'href': a.get('href') or '', 'name': a.get('aria-label') or '',
                            'target': a.get('target') or '', 'rel': a.get('rel') or ''}
            self.links.append(self.current)
        if tag in ('input', 'select', 'textarea') and (a.get('type') or '').lower() not in ('hidden', 'submit', 'button'):
            self.controls.append((a.get('id'), a.get('aria-label') or a.get('aria-labelledby') or ''))

    def handle_data(self, data):
        if self.current:
            self.current['name'] += data.strip() + ' '

    def handle_endtag(self, tag):
        if tag == 'a':
            self.current = None

def audit(html):
    p = Audit()
    p.feed(html)
    problems = []
    checkout = 0
    for link in p.links:
        href = link['href'].strip()
        name = link['name'].strip()
        if not href or href.startswith(('javascript:', 'data:')):
            problems.append('unsafe_or_empty_link')
        if not name:
            problems.append('unnamed_link')
        if '/checkout/' in urlsplit(href).path:
            checkout += 1
            if not name:
                problems.append('unnamed_checkout')
        if link['target'].lower() == '_blank' and 'noopener' not in link['rel'].lower().split():
            problems.append('external_tab_missing_noopener')
    for control_id, name in p.controls:
        if not name and (not control_id or control_id not in p.labels):
            problems.append('unlabelled_form_control')
    if checkout == 0:
        problems.append('no_checkout_link')
    return {'checkout_links': checkout, 'issues': sorted(set(problems)), 'passed': not problems}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('snapshot', type=Path, help='Authorized local HTML copy; never a live URL')
    args = ap.parse_args()
    if not args.snapshot.is_file() or args.snapshot.suffix.lower() not in ('.html', '.htm'):
        ap.error('local HTML snapshot required')
    report = audit(args.snapshot.read_text(encoding='utf-8'))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if report['passed'] else 2)

if __name__ == '__main__':
    main()
