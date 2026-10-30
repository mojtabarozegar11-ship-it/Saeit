#!/usr/bin/env python3
"""Static-only accessible-name audit for S-01 checkout/invoice/download HTML.

This does not access production, verify payments, or authorize deployment.
"""
from html.parser import HTMLParser
import argparse
import json
from pathlib import Path
import sys


class MarkupAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.issues = []
        self.labels_for = set()
        self.inputs = []
        self.open_names = []
        self.label_depth = 0
        self.controls = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'label':
            self.label_depth += 1
            if a.get('for'):
                self.labels_for.add(a['for'])
        if tag in ('button', 'a'):
            self.open_names.append({'tag': tag, 'attrs': a, 'text': ''})
        if tag in ('input', 'select', 'textarea'):
            if tag != 'input' or a.get('type', 'text').lower() not in ('hidden', 'submit', 'button'):
                self.inputs.append((tag, a, self.label_depth > 0))
        if tag == 'img' and 'alt' not in a and not a.get('aria-label'):
            self.issues.append('img missing alt')
        if tag == 'a' and a.get('href', '').strip().lower().startswith(('javascript:', 'data:')):
            self.issues.append('unsafe anchor URL')
        if tag == 'form' and a.get('action', '').strip().lower().startswith(('javascript:', 'data:')):
            self.issues.append('unsafe form action')

    def handle_data(self, data):
        for item in self.open_names:
            item['text'] += data

    def handle_endtag(self, tag):
        if tag == 'label' and self.label_depth:
            self.label_depth -= 1
        if tag in ('a', 'button'):
            for i in range(len(self.open_names) - 1, -1, -1):
                item = self.open_names[i]
                if item['tag'] != tag:
                    continue
                self.open_names.pop(i)
                a = item['attrs']
                name = item['text'].strip() or a.get('aria-label', '').strip() or a.get('aria-labelledby', '').strip() or a.get('title', '').strip()
                if not name:
                    self.issues.append(f'{tag} missing accessible name')
                if tag == 'a' and a.get('href', '').strip() in ('', '#'):
                    self.issues.append('anchor has placeholder href')
                self.controls += 1
                break


def audit_html(html):
    parser = MarkupAudit()
    parser.feed(html)
    parser.close()
    for tag, a, implicit in parser.inputs:
        if implicit or (a.get('id') and a['id'] in parser.labels_for):
            continue
        if any(str(a.get(k, '')).strip() for k in ('aria-label', 'aria-labelledby', 'title')):
            continue
        if tag == 'input' and a.get('type', '').lower() == 'image' and a.get('alt', '').strip():
            continue
        parser.issues.append(f'{tag} missing associated label/accessible name')
    return {'status': 'PASS' if not parser.issues else 'FAIL',
            'issues': parser.issues, 'controls': parser.controls + len(parser.inputs),
            'scope': 'static-only; not a payment or production verification'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('html', type=Path)
    a = p.parse_args()
    if not a.html.is_file() or a.html.suffix.lower() not in ('.html', '.htm'):
        p.error('Expected a local HTML file')
    result = audit_html(a.html.read_text(encoding='utf-8'))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
