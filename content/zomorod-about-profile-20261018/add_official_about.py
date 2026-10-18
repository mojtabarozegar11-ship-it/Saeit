#!/usr/bin/env python3
"""Add the official scientific profile to the existing /about/ page.

Only writes a candidate HTML file. The original About file and its historical
sections must remain byte-identical after removing our clearly marked insert.
"""
import argparse
import re
from pathlib import Path

START = '<!-- zm-about-official-scientific-profile-20261018 -->'
CSS_ID = 'zm-about-official-theme-20261018'

def patch(source: str, section: str) -> str:
    if START in source or CSS_ID in source:
        raise ValueError('Already contains the official research profile')
    if not section.startswith(START) or section.count(START) != 1 or section.count(CSS_ID) != 1:
        raise ValueError('Invalid content fragment or duplicate marker')
    if not re.search(r'<html\b[^>]*\blang=["\x27]fa["\x27]',source,re.I):
        raise ValueError('Expected Persian original About page')
    if source.count('</head>') != 1 or source.count('</body>') != 1:
        raise ValueError('Unexpected page structure')
    if 'زمرد ملل' not in source or 'ریشه در تجربه' not in source:
        raise ValueError('Unexpected About page identity; no changes permitted')
    if 'zm-unified-v7-20261018' not in source:
        raise ValueError('Protected company header is absent')
    if section.count('<details') != 7 or section.count('<article>') != 33:
        raise ValueError('Incomplete multi-section scientific profile')
    header = re.search(r'<header\b[^>]*class=["\x27][^"\x27]*zm-v7-header[^"\x27]*["\x27][^>]*>', source, re.I)
    if not header:
        raise ValueError('Existing shared header missing; refuse to guess placement')
    end = source.find('</header>',header.end())
    if end < 0:
        raise ValueError('Header closing tag missing')
    end += len('</header>')
    candidate = source[:end] + '\n' + section + '\n' + source[end:]
    assert candidate.replace('\n' + section + '\n', '', 1) == source
    assert candidate.count(START) == 1
    assert candidate.endswith(source[end:])
    assert len(candidate.encode('utf-8')) > len(source.encode('utf-8')) + 10000
    assert candidate.strip().endswith('</html>')
    return candidate

def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('fragment', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Refuse to overwrite any staged output')
    original = args.source.read_text(encoding='utf-8')
    fragment = args.fragment.read_text(encoding='utf-8')
    candidate = patch(original,fragment)
    args.output.write_text(candidate,encoding='utf-8')
    print('ABOUT_SCIENTIFIC_PROFILE_VALIDATED=yes')
    print('SEVEN_CHAPTERS=verified')
    print('THIRTY_THREE_SUBJECTS=verified')
    print('PREEXISTING_ABOUT_CONTENT=byte_preserved')

if __name__ == '__main__':
    main()
