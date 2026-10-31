#!/usr/bin/env python3
"""Local-only chapter omission triage for two markdown book drafts.

Does not transmit content or judge originality/rights. Chapter headings must be
'## Chapter N ...' in both files. Output is aggregate CSV with no manuscript text.
"""
import argparse
import csv
import re
from collections import OrderedDict
from pathlib import Path

CHAPTER = re.compile(r'^##\s+(?:Chapter|CHAPTER)\s+(\d+)\b.*$', re.M)
WORD = re.compile(r"\b[\w'-]+\b", re.UNICODE)
URL = re.compile(r'https?://[^\s)<>]+')


def extract(text):
    matches = list(CHAPTER.finditer(text))
    if not matches:
        raise ValueError('No ## Chapter N headings found; do not assume alignment')
    chapters = OrderedDict()
    for i, match in enumerate(matches):
        num = int(match.group(1))
        if num in chapters:
            raise ValueError(f'Duplicate chapter {num}')
        content = text[match.end():matches[i+1].start() if i+1 < len(matches) else len(text)]
        chapters[num] = {'words': len(WORD.findall(content)),
                         'url_count': len(URL.findall(content)),
                         'citation_markers': len(re.findall(r'\[[0-9]+\]|\([A-Z][\w-]+,?\s+20\d{2}\)', content))}
    return chapters


def compare(old, new):
    a, b = extract(old), extract(new)
    rows = []
    for n in sorted(set(a) | set(b)):
        o, v = a.get(n), b.get(n)
        oldwords = o['words'] if o else 0
        newwords = v['words'] if v else 0
        delta = newwords-oldwords
        flags = []
        if not v: flags.append('MISSING_CHAPTER')
        if not o: flags.append('NEW_CHAPTER')
        if o and v and oldwords and delta / oldwords <= -.20: flags.append('WORD_LOSS_GE_20_PERCENT')
        if o and v and v['url_count'] < o['url_count']: flags.append('FEWER_URLS')
        if o and v and v['citation_markers'] < o['citation_markers']: flags.append('FEWER_CITATION_MARKERS')
        rows.append({'chapter': n, 'old_words': oldwords, 'new_words': newwords,
                     'delta_words': delta, 'old_urls': o['url_count'] if o else 0,
                     'new_urls': v['url_count'] if v else 0,
                     'flags': ';'.join(flags)})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('older_md',type=Path);p.add_argument('newer_md',type=Path)
    p.add_argument('output_csv',type=Path)
    args=p.parse_args()
    rows=compare(args.older_md.read_text(encoding='utf-8'),
                 args.newer_md.read_text(encoding='utf-8'))
    with args.output_csv.open('x',encoding='utf-8',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print({'chapters_compared':len(rows),'flagged':sum(bool(r['flags']) for r in rows),
           'old_words':sum(r['old_words'] for r in rows),
           'new_words':sum(r['new_words'] for r in rows),
           'manual_review_required':True})

if __name__=='__main__':
    main()
