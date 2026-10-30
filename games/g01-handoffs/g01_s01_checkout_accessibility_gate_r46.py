#!/usr/bin/env python3
"""Offline checkout/invoice/download HTML accessibility preflight for S-01.

No network requests, payments, browser automation, or site changes. This is a
pre-merge QA aid, NOT a live transaction or a deployment authorization.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import sys


class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.issues = []
        self.elements = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'button', 'a', 'label'}:
            self._stack.append({'tag': tag, 'attrs': attrs, 'text': ''})
        if tag == 'img' and not (attrs.get('alt') is not None or attrs.get('aria-label')):
            self.issues.append('img missing alt text (empty alt is valid for decoration)')
        if tag == 'input' and attrs.get('type', 'text').lower() not in {'hidden', 'submit', 'button', 'image'}:
            if not (attrs.get('id') or attrs.get('aria-label') or attrs.get('aria-labelledby') or attrs.get('title')):
                self.issues.append('input missing id/accessible name for label association')
        if tag == 'a' and attrs.get('href', '').strip().lower().startswith(('javascript:', 'data:')):
            self.issues.append('unsafe inline link target')
        if tag == 'form' and attrs.get('action', '').strip().lower().startswith(('javascript:', 'data:')):
            self.issues.append('unsafe form action')

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]['text'] += data

    def handle_endtag(self, tag):
        if self._stack and self._stack[-1]['tag'] == tag:
            item = self._stack.pop()
            attrs, name = item['attrs'], item['text'].strip()
            if tag in {'a', 'button'} and not (name or attrs.get('aria-label') or attrs.get('aria-labelledby') or attrs.get('title')):
                self.issues.append(f'{tag} missing accessible name')
            if tag == 'a' and attrs.get('href', '').strip() in {'', '#'}:
                self.issues.append('anchor has empty/placeholder href')
            self.elements.append({'tag': tag, 'name': name[:120]})


def audit_html(content):
    parser = Audit()
    parser.feed(content)
    parser.close()
    return {'status': 'PASS' if not parser.issues else 'FAIL',
            'issues': parser.issues, 'controls': len(parser.elements),
            'scope': 'offline-static-only; no payment or live release verified'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('html', type=Path, help='Local, authorized HTML artifact only')
    args = ap.parse_args()
    if not args.html.is_file() or args.html.suffix.lower() not in {'.html', '.htm'}:
        ap.error('Expected an existing local HTML file')
    result = audit_html(args.html.read_text(encoding='utf-8'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
