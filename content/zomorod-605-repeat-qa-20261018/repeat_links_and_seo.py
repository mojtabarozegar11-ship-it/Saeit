#!/usr/bin/env python3
"""Second-pass, additive QA of every existing Zomorod homepage card destination.

This deliberately does not fabricate 605 new articles or overwrite original
scientific text. It ensures each URL has its own real document, title, meta
description, canonical and JSON-LD; adds crawlable related-topic links; and
announces the existing topic sitemap in robots.txt.

Inputs must be private copies of production. Nothing writes to production.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PASS = 'zm-card-repeat-audit-related-20261018'
BASE = 'https://zomorodmelal.ir'
MANIFEST_RE = re.compile(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>', re.S)
SITEMAP_LINE = 'Sitemap: https://zomorodmelal.ir/topics/sitemap.xml'
EXPECTED = 605
RESEARCH_COUNT = 60
TOPIC_COUNT = 545

def h(v: str) -> str:
    return html.escape(v, quote=True)

def source_manifest(index_html: str):
    matches = list(MANIFEST_RE.finditer(index_html))
    if len(matches) != 1:
        raise ValueError('Expected one original homepage manifest')
    rows = json.loads(matches[0].group(1))['rows']
    if len(rows) != 29 or sum(len(r['cards']) for r in rows) != EXPECTED:
        raise ValueError('Unexpected count: original 29 rows/605 cards not verified')
    if [r['id'] for r in rows if r['index'] > 26] != ['ZM-R27', 'ZM-R28', 'ZM-R29']:
        raise ValueError('Unexpected research shelf manifest')
    all_ids = [c['id'] for r in rows for c in r['cards']]
    if len(set(all_ids)) != EXPECTED:
        raise ValueError('Duplicate card IDs')
    paths = [c.get('canonicalUrl') for r in rows for c in r['cards']]
    if len(set(paths)) != EXPECTED:
        raise ValueError('Duplicate card destinations')
    if sum(p.startswith('/topics/') for p in paths) != TOPIC_COUNT:
        raise ValueError('545 independent topic URLs not found')
    if sum(p.startswith('/research/directory/') for p in paths) != RESEARCH_COUNT:
        raise ValueError('60 independent research URLs not found')
    return rows

def pick_relative(card, root_topics: Path, root_research: Path) -> Path:
    path = card['canonicalUrl']
    if path.startswith('/topics/'):
        rest = path.removeprefix('/topics/')
        root = root_topics
    elif path.startswith('/research/directory/'):
        rest = path.removeprefix('/research/directory/')
        root = root_research
    else:
        raise ValueError('Unknown card destination: '+path)
    if not re.fullmatch(r'[a-z0-9-]+(?:/[a-z0-9-]+)*/',rest):
        raise ValueError('Unsafe card URL: '+path)
    doc = root / rest / 'index.html'
    if not doc.is_file() or doc.is_symlink():
        raise ValueError('Missing or linked destination: '+str(doc))
    return doc

def check_page(doc: Path, card: dict):
    raw = doc.read_text(encoding='utf-8')
    title = card['title']
    canon = BASE + card['canonicalUrl']
    if raw.count('<h1') != 1 or '</h1>' not in raw:
        raise ValueError('Invalid page heading: '+str(doc))
    if title not in raw:
        raise ValueError('Wrong subject in page: '+str(doc))
    match = re.search(r'<title>([^<]+)</title>',raw,re.I)
    if not match or title not in html.unescape(match.group(1)):
        raise ValueError('Unrelated SEO title: '+str(doc))
    meta = re.search(r'<meta\s+name="description"\s+content="([^"]+)"',raw,re.I)
    if not meta:
        raise ValueError('Missing topic meta description: '+str(doc))
    if title not in html.unescape(meta.group(1)):
        # Some original research-directory pages describe the scientific subject
        # without naming it in the meta description. Prefix its exact H1/card name.
        old_desc=html.unescape(meta.group(1))
        improved=f'{title}؛ {old_desc}'
        if len(improved)>190:
            improved=improved[:185].rstrip(' ،.؛')+'…'
        raw=raw[:meta.start(1)]+h(improved)+raw[meta.end(1):]
        assert title in improved
    canonical = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"',raw,re.I)
    if not canonical or canonical.group(1) != canon:
        raise ValueError('Missing canonical matching linked URL: '+str(doc))
    if re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex',raw,re.I):
        raise ValueError('Topic inadvertently noindex: '+str(doc))
    if 'property="og:title"' not in raw or 'property="og:description"' not in raw:
        raise ValueError('Missing OpenGraph page metadata: '+str(doc))
    data = re.findall(r'<script\s+type="application/ld\+json">(.*?)</script>',raw,re.S)
    if not data:
        raise ValueError('Missing schema: '+str(doc))
    for schema in data:
        json.loads(schema)
    if raw.count('</main>') != 1:
        raise ValueError('Unexpected page markup: '+str(doc))
    if PASS in raw:
        raise ValueError('Already passed previously; refuse duplicate insertion')
    if len(re.sub(r'<[^>]+>','',raw).strip()) < 900:
        raise ValueError('Page is nearly empty: '+str(doc))
    return raw

def build_related(row, i):
    cards=row['cards']
    focus=cards[i]
    n=len(cards)
    other_indices=[(i+k)%n for k in (1,2,-1,-2)]
    unique = []
    seen={i}
    for j in other_indices:
        if j not in seen:
            seen.add(j)
            unique.append(cards[j])
    assert len(unique)==4
    links = ''.join(
        f'<li><a href="{h(c["canonicalUrl"])}" title="{h(c["title"]+"؛ "+row["title"])}">{h(c["title"])}</a></li>'
        for c in unique
    )
    return (f'<!-- {PASS} -->\n'
        '<section class="zm-related-subjects" aria-label="موضوعات علمی مرتبط" '
        'style="margin:26px auto;padding:21px;border:1px solid #c3a56780;'
        'border-radius:18px;background:#17392d;color:#f2e9d0;max-width:1120px">'
        f'<h2 style="color:#f5d793;font-size:22px">مطالعه موضوعات مرتبط با {h(focus["title"])}</h2>'
        f'<p>موضوع «{h(focus["title"])}» در مجموعه «{h(row["title"])}» قرار دارد. '
        'برای مقایسه روش‌ها، شاخص‌ها و شرایط کاربرد، صفحات تخصصی نزدیک را نیز بررسی کنید.</p>'
        f'<ul style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:13px;'
        'padding:0 24px;line-height:2">'+links+'</ul>'
        '<p><a style="color:#f5d793" href="/topics/">فهرست همه حوزه‌ها و صفحات تخصصی زمرد ملل ←</a></p>'
        '</section>\n')

def audit_and_enrich(home: Path, topics: Path, research: Path, original_robots: Path, new_robots: Path):
    rows=source_manifest(home.read_text(encoding='utf-8'))
    if not (topics/'.htaccess').is_file():
        raise ValueError('Missing Passenger bypass for existing static topics')
    if 'PassengerEnabled off' not in (topics/'.htaccess').read_text():
        raise ValueError('Topic static host configuration mismatch')
    if len(list(topics.rglob('index.html'))) != TOPIC_COUNT + 1:
        raise ValueError('Unexpected topic article count')
    if len(list(research.rglob('index.html'))) != RESEARCH_COUNT:
        raise ValueError('Unexpected research article count')
    sitemap = ET.parse(topics/'sitemap.xml').getroot()
    site_urls = {e.text for e in sitemap.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    intended = {BASE+'/topics/'} | {
        BASE+c['canonicalUrl'] for row in rows for c in row['cards']}
    if site_urls != intended or len(site_urls) != EXPECTED+1:
        raise ValueError('Sitemap does not cover all 605 unique card destinations')
    seen_pages=set()
    original_content=[]
    for row in rows:
        for i, card in enumerate(row['cards']):
            doc=pick_relative(card,topics,research)
            if doc in seen_pages:
                raise ValueError('Two cards share one HTML file')
            seen_pages.add(doc)
            old=check_page(doc,card)
            related=build_related(row,i)
            edited=old.replace('</main>',related+'</main>',1)
            assert edited.replace(related,'',1)==old
            assert edited.count(PASS)==1
            doc.write_text(edited,encoding='utf-8')
            original_content.append((str(doc),len(old),len(edited)))
    assert len(seen_pages)==EXPECTED
    # Announce the previously unadvertised topic XML sitemap to search crawlers.
    robots=original_robots.read_text(encoding='utf-8')
    if not robots.strip() or 'Sitemap: https://zomorodmelal.ir/sitemap.xml' not in robots:
        raise ValueError('Cannot establish original robots directives')
    if SITEMAP_LINE in robots:
        raise ValueError('New sitemap already announced; refuse duplicate')
    if new_robots.exists():
        raise ValueError('Refuse to overwrite candidate robots file')
    update=robots.rstrip('\n')+'\n'+SITEMAP_LINE+'\n'
    assert update.replace(SITEMAP_LINE+'\n','',1)==robots.rstrip('\n')+'\n'
    new_robots.write_text(update,encoding='utf-8')
    output={
      "cards":EXPECTED,"newIndependentTopicsPreserved":TOPIC_COUNT,
      "existingResearchPagesPreserved":RESEARCH_COUNT,"topicSitemapUrls":606,
      "verifiedIndependentHTMLDocs":len(seen_pages),
      "pagesWithCrawlableRelatedSubjectLinks":len(original_content),
      "robotsOriginalUnchangedBeforeAppend":True,
      "addedSitemap":SITEMAP_LINE,
      "pageTotalBytesBefore":sum(p[1] for p in original_content),
      "pageTotalBytesAfter":sum(p[2] for p in original_content),
      "protectedOriginalScientificText":"kept; added related navigation only"
    }
    print("SCIENTIFIC_TOPIC_QA="+json.dumps(output,ensure_ascii=False))
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--home',type=Path,required=True)
    p.add_argument('--topics',type=Path,required=True)
    p.add_argument('--research',type=Path,required=True)
    p.add_argument('--robots',type=Path,required=True)
    p.add_argument('--robots-output',type=Path,required=True)
    a=p.parse_args()
    audit_and_enrich(a.home,a.topics,a.research,a.robots,a.robots_output)

if __name__=='__main__':
    main()
