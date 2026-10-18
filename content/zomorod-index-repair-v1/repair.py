#!/usr/bin/env python3
"""Stage-only Zomorod root page repair and canonical sitemap; no direct production writes."""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import hashlib
from pathlib import Path
from urllib.parse import quote
from xml.etree.ElementTree import Element, SubElement, tostring

DOMAIN = 'https://zomorodmelal.ir'
BANNED = {'mohammad','ghanadi','amozeshgah','tala','education','business','site-heritage','static','admin','cgi-bin','private','app','wp-admin','zm-agriculture-guides'}
THEME = '<link rel="stylesheet" href="/static/site/zomorod-v10/inner-v10.css?v=20261018" data-zm-v10="shared-theme">'

def safe(root: Path, f: Path):
    if not f.is_file() or f.is_symlink():
        raise RuntimeError(f'unsafe or missing file: {f}')
    if not f.resolve().is_relative_to(root.resolve()):
        raise RuntimeError('out of root')
    for p in [f, *f.parents]:
        if p == root: break
        if p.is_symlink(): raise RuntimeError('symlinked parent')

def load_skin(path: Path):
    spec = importlib.util.spec_from_file_location('zomorod_v7_patch', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def html_attr(source, name):
    m = re.search(r'<html\b([^>]*)>', source, re.I)
    if not m: return None
    a = re.search(r'\b' + name + r'\s*=\s*["\x27]([^"\x27]+)', m.group(1), re.I)
    return a.group(1) if a else None

def sitemap_urls(root: Path):
    found = set()
    for p in root.rglob('index.html'):
        rel = p.relative_to(root)
        if any(x in BANNED or x.startswith('__') or x.startswith('.') for x in rel.parts): continue
        if len(rel.parts) > 7 or p.is_symlink(): continue
        if any((root.joinpath(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts))): continue
        src = p.read_text(encoding='utf-8')
        if html_attr(src,'lang') != 'fa': continue
        if re.search(r'<meta\b[^>]*content=["\x27][^"\x27]*noindex',src,re.I):continue
        m = re.search(r'<link\b[^>]*\brel=["\x27]canonical["\x27][^>]*>',src,re.I)
        if not m: continue
        a = re.search(r'\bhref=["\x27]([^"\x27]+)',m.group(0),re.I)
        route = '/' + '/'.join(rel.parts[:-1]) + ('/' if len(rel.parts)>1 else '')
        if a and a.group(1)==DOMAIN+route: found.add(DOMAIN+quote(route,safe='/'))
    return sorted(found)

def build(root:Path, output:Path, skin:Path):
    root = root.resolve(strict=True)
    if output.exists():raise RuntimeError('candidate folder already exists')
    if root.is_symlink():raise RuntimeError('symlink root')
    safe(root,root/'index.html')
    if not (root/'static/site/zomorod-v7/inner-v7.css').is_file():raise RuntimeError('missing V7 shared CSS')
    if not (root/'static/site/zomorod-v10/inner-v10.css').is_file():raise RuntimeError('missing V10 shared CSS')
    for missing in ('robots.txt','sitemap.xml'):
        if (root/missing).exists() or (root/missing).is_symlink():raise RuntimeError('existing SEO file must not be overwritten: '+missing)
    updater = load_skin(skin)
    targets = sorted((root/'research/directory').rglob('index.html'))
    assert len(targets)==60, ('unexpected research directory count', len(targets))
    targets.append(root/'search/index.html')
    originals = []
    output.mkdir(mode=0o700,parents=True)
    for p in targets:
        safe(root,p)
        rel = p.relative_to(root)
        before = p.read_bytes()
        source = before.decode('utf-8')
        assert html_attr(source,'lang')=='fa',rel
        assert updater.MARKER not in source and 'data-zm-v10="shared-theme"' not in source, rel
        changed = updater.patch(before,rel).decode('utf-8')
        changed = changed.replace('</head>',THEME+'</head>',1)
        if rel.parts==('search','index.html'):
            changed = changed.replace('</head>','<meta name="robots" content="noindex,follow"></head>',1)
        main = re.search(r'<main\b[^>]*>[\s\S]*?</main>',source,re.I)
        if main and main.group(0) not in changed:raise RuntimeError('main editorial content not preserved: '+str(rel))
        assert len(changed)>len(source) and changed.count('</body>')==1
        out = output/rel
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(changed,encoding='utf-8')
        originals.append({'path':str(rel),'old_sha256':hashlib.sha256(before).hexdigest(),'new_sha256':hashlib.sha256(changed.encode()).hexdigest()})
    urls = sitemap_urls(root)
    assert 85 <= len(urls) <= 120, ('unexpected canonical URL count',len(urls))
    assert DOMAIN+'/' in urls and DOMAIN+'/research/' in urls
    assert DOMAIN+'/research/directory/laboratories/molecular-genetics/' in urls
    element=Element('urlset',{'xmlns':'http://www.sitemaps.org/schemas/sitemap/0.9'})
    for url in urls:SubElement(SubElement(element,'url'),'loc').text=url
    (output/'sitemap.xml').write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n'+tostring(element,encoding='utf-8')+b'\n')
    (output/'robots.txt').write_text('User-agent: *\nDisallow: /admin/\nDisallow: /site-heritage/\nDisallow: /__zm_\nDisallow: /zm-agriculture-guides/\nSitemap: '+DOMAIN+'/sitemap.xml\n',encoding='utf-8')
    manifest={'pages':originals,'sitemap_count':len(urls),'language':'fa','added_files':['robots.txt','sitemap.xml']}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('STAGED_MAIN_PAGES',len(originals),'UNIQUE_CANONICAL_URLS',len(urls),'ORIGINAL_BYTES_PRESERVED=1')
    return manifest

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('docroot',type=Path);ap.add_argument('candidate',type=Path);ap.add_argument('skin',type=Path)
    args=ap.parse_args();build(args.docroot,args.candidate,args.skin)
