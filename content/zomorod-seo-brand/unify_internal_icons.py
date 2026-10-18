#!/usr/bin/env python3
"""Update favicon references in only existing main-domain HTML, without changing article bodies."""
from pathlib import Path
import re,sys,hashlib,json
root=Path(sys.argv[1]).resolve()
out=Path(sys.argv[2]).resolve()
assert not out.exists()
ex={'mohammad','ghanadi','amozeshgah','tala','business','site-heritage','admin','education','static','private','cgi-bin'}
targets=[]
for p in root.rglob('index.html'):
    if p.is_symlink():continue
    rel=p.relative_to(root)
    if len(rel.parts)>6 or any(x in ex or x.startswith('.') or x.startswith('__') for x in rel.parts):continue
    if str(rel)=='index.html':continue
    s=p.read_text('utf-8')
    if 'zm-unified-v7-20261018' not in s and 'zm-v7-header' not in s:continue
    if s.lower().count('</head>')!=1 or not re.search(r'<main\b.*?</main\s*>',s,re.I|re.S):continue
    if 'zm-official-favicon-all-internal-20261018' in s:continue
    targets.append((p,rel,s))
assert 35<=len(targets)<=80,len(targets)
out.mkdir(parents=True)
data=[]
favicon='<link rel="icon" type="image/x-icon" sizes="any" href="/favicon.ico?v=20261018"><link rel="icon" type="image/png" sizes="192x192" href="/static/site/zomorod-brand-20261018/icon-192.png"><link rel="apple-touch-icon" sizes="180x180" href="/static/site/zomorod-brand-20261018/icon-180.png">'
for p,rel,s in targets:
    main=re.search(r'<main\b.*?</main\s*>',s,re.I|re.S).group()
    h,b=s.split('</head>',1)
    h=re.sub(r'<link\b(?=[^>]*\brel\s*=\s*["\'](?:shortcut icon|icon|apple-touch-icon)["\'])[^>]*>','',h,flags=re.I)
    updated=h+'<!-- zm-official-favicon-all-internal-20261018 -->'+favicon+'</head>'+b
    assert re.search(r'<main\b.*?</main\s*>',updated,re.I|re.S).group()==main
    assert updated.count('zm-official-favicon-all-internal-20261018')==1
    target=out/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(updated,encoding='utf-8')
    data.append({'path':str(rel),'before':hashlib.sha256(s.encode()).hexdigest()})
(out/'manifest.json').write_text(json.dumps(data,ensure_ascii=False))
print('FAVICON_INTERNAL_PREPARED='+str(len(data)))
