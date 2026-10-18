#!/usr/bin/env python3
"""Prepare only: update root/main-site HTML favicon + organization brand, never write live until release gate."""
import argparse, json, re, hashlib
from pathlib import Path
BRAND='شرکت کشت و صنعت زمرد ملل'
LATIN='Zomorod Mell'
ASSETS='/static/site/zomorod-brand-20261018'
EXCLUDED={'tala','business','mohammad','ghanadi','amozeshgah','site-heritage','static','admin','education','private','cgi-bin'}
TAG='zm-official-brand-icon-20261018'
ICON=f'<link rel="icon" type="image/x-icon" sizes="any" href="/favicon.ico?v=20261018"><link rel="icon" type="image/png" sizes="192x192" href="{ASSETS}/icon-192.png"><link rel="apple-touch-icon" sizes="180x180" href="{ASSETS}/icon-180.png">'
ORG={'@context':'https://schema.org','@type':'Organization','@id':'https://zomorodmelal.ir/#organization','name':BRAND,'alternateName':['زمرد ملل',LATIN,'Zomorod Melal'],'url':'https://zomorodmelal.ir/','logo':'https://zomorodmelal.ir'+ASSETS+'/icon-192.png'}
def patch(s,rel):
    assert TAG not in s and s.lower().count('</head>')==1
    original_main=re.search(r'<main\b.*?</main\s*>',s,re.I|re.S)
    assert original_main,rel
    s=re.sub(r'<link\b(?=[^>]*\brel\s*=\s*["\'](?:shortcut icon|icon|apple-touch-icon)["\'])[^>]*>', '',s,flags=re.I)
    if rel=='index.html':
        s=re.sub(r'<title\b[^>]*>.*?</title>',f'<title>{BRAND} | {LATIN}</title>',s,flags=re.I|re.S,count=1)
        s=re.sub(r'(<meta\b[^>]*property=["\']og:site_name["\'][^>]*content=["\'])[^"\']*(["\'])',lambda m:m.group(1)+BRAND+m.group(2),s,flags=re.I)
    org=''
    if rel in ('index.html','company/index.html','about/index.html'):
        org='<script type="application/ld+json" data-zm-brand="organization">'+json.dumps(ORG,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+'</script>'
    meta=f'<meta name="application-name" content="{BRAND} | {LATIN}"><meta property="og:image" content="https://zomorodmelal.ir{ASSETS}/icon-192.png">'
    # Keep existing on-page headings and all article text unchanged.
    s=s.replace('</head>',f'<!-- {TAG} -->'+ICON+meta+org+'</head>',1)
    assert re.search(r'<main\b.*?</main\s*>',s,re.I|re.S).group(0)==original_main.group(0),rel
    assert s.count(TAG)==1
    return s

def main():
    ap=argparse.ArgumentParser();ap.add_argument('webroot',type=Path);ap.add_argument('--output',required=True,type=Path)
    x=ap.parse_args();root=x.webroot.resolve();out=x.output
    assert (root/'index.html').is_file() and not out.exists()
    paths=[]
    for p in root.rglob('index.html'):
        if p.is_symlink():continue
        rel=p.relative_to(root)
        if len(rel.parts)>6 or any(x in EXCLUDED or x.startswith('.') or x.startswith('__') for x in rel.parts):continue
        s=p.read_text(encoding='utf-8')
        if 'zm-unified-v7-20261018' not in s and str(rel)!='index.html':continue
        paths.append((p,rel,s))
    # Unique main-site pages, do not accidentally include private sub-sites.
    assert 40<=len(paths)<=75,len(paths)
    out.mkdir(parents=True)
    result=[]
    for p,rel,s in paths:
        updated=patch(s,str(rel));dest=out/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(updated,encoding='utf-8')
        result.append({'path':str(rel),'before_sha':hashlib.sha256(s.encode()).hexdigest(),'after_sha':hashlib.sha256(updated.encode()).hexdigest()})
    (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print('BRAND_PAGES_PREPARED='+str(len(paths)))

if __name__=='__main__':main()