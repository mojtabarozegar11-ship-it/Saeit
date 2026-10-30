#!/usr/bin/env python3
"""G-01 to S-01: read-only local static HTML asset gate; no deploy/network."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

class Assets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'img', 'source', 'video', 'audio') and a.get('src'):
            self.refs.append(a['src'])
        if tag == 'link' and a.get('href') and a.get('rel') in ('stylesheet', 'icon'):
            self.refs.append(a['href'])

def audit(root, entry='index.html'):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('root must be a directory')
    page = root / entry
    if page.is_symlink() or not page.resolve().is_relative_to(root):
        raise ValueError('unsafe entry')
    parser = Assets()
    parser.feed(page.read_text(encoding='utf-8'))
    checked, errors = [], []
    for raw in parser.refs:
        u = urlsplit(raw)
        if u.scheme or u.netloc or raw.startswith('//') or raw.startswith('#'):
            continue  # External URLs need a separate network/rights gate.
        if not u.path or u.path.startswith('/') or '%2f' in u.path.lower() or '%5c' in u.path.lower():
            errors.append('unsafe URL: ' + raw)
            continue
        decoded = unquote(u.path)
        path = page.parent / decoded
        if '\\' in decoded or any(part in ('.', '..') for part in Path(decoded).parts) or path.is_symlink():
            errors.append('unsafe path: ' + raw)
            continue
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            errors.append('missing/escaping asset: ' + raw)
            continue
        checked.append(decoded)
    return checked, errors

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root')
    p.add_argument('--entry', default='index.html')
    a = p.parse_args()
    checked, errors = audit(a.root, a.entry)
    print('CHECKED', len(checked), 'LOCAL_ASSETS')
    for error in errors:
        print('FAIL', error)
    if errors:
        raise SystemExit(1)
    print('PASS static local assets; NOT a browser, payment or deployment acceptance')
