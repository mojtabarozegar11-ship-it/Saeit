#!/usr/bin/env python3
"""G-01 -> S-01: offline static accessibility preflight. No network, no customer data output."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path

class Scanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buttons = 0
        self.unlabeled_buttons = 0
        self.blank_links_without_noopener = 0
        self.download_links_missing_href = 0
        self._button_stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'button':
            self.buttons += 1
            self._button_stack.append({'label': bool((a.get('aria-label') or a.get('title') or '').strip()), 'text': ''})
        elif tag == 'a':
            rel = set((a.get('rel') or '').lower().split())
            if (a.get('target') or '').lower() == '_blank' and not ({'noopener', 'noreferrer'} & rel):
                self.blank_links_without_noopener += 1
            if 'download' in a and not (a.get('href') or '').strip():
                self.download_links_missing_href += 1

    def handle_data(self, data):
        if self._button_stack:
            self._button_stack[-1]['text'] += data

    def handle_endtag(self, tag):
        if tag == 'button' and self._button_stack:
            button = self._button_stack.pop()
            if not button['label'] and not button['text'].strip():
                self.unlabeled_buttons += 1

    def summary(self):
        counts = {
            'buttons': self.buttons,
            'unlabeled_buttons': self.unlabeled_buttons,
            'blank_links_without_noopener': self.blank_links_without_noopener,
            'download_links_missing_href': self.download_links_missing_href,
        }
        return {'pass': not any(v for k,v in counts.items() if k != 'buttons'), 'counts': counts,
                'scope': 'static markup only; no browser, payments, invoice delivery or live-site validation'}

def scan(text):
    parser = Scanner()
    parser.feed(text)
    parser.close()
    return parser.summary()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('html', type=Path, help='authorized offline HTML copy')
    args = ap.parse_args()
    if not args.html.is_file() or args.html.is_symlink():
        ap.error('regular local HTML file required')
    result = scan(args.html.read_text(encoding='utf-8'))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(0 if result['pass'] else 2)

if __name__ == '__main__':
    main()
