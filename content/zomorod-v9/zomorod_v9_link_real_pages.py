#!/usr/bin/env python3
"""Link verified existing Zomorod Melal pages inside matching V8 shelves.

No rows/pages removed, no invented URLs, and never touches other files itself.
The deployment workflow provides backup, SHA protection and atomic replacement.
"""
import argparse,base64,hashlib,json,re,os
from pathlib import Path
from xml.sax.saxutils import escape

VERSION='zm-v9-real-pages-unique-links-20261018'
# exact existing page -> appropriate shelf + preferred existing card slug (or new distinct label)
ROUTES=[
 ('/','ZM-R16','zomorod-portal',None),
 ('/agriculture/','ZM-R01',None,'کشاورزی و خدمات روستایی'),
 ('/agriculture/horticulture/','ZM-R02',None,'راهنمای باغبانی'),
 ('/agriculture/greenhouse/','ZM-R03',None,'راهنمای گلخانه'),
 ('/agriculture/livestock/','ZM-R04',None,'راهنمای دامپروری'),
 ('/agriculture/poultry/','ZM-R05',None,'راهنمای پرورش طیور'),
 ('/agriculture/aquaculture/','ZM-R06',None,'راهنمای آبزی‌پروری'),
 ('/agriculture/inputs/','ZM-R07',None,'نهاده‌های کشاورزی'),
 ('/agriculture/seeds/','ZM-R07','seed-production',None),
 ('/agriculture/fertilizers/','ZM-R07',None,'کود و تغذیه گیاه'),
 ('/agriculture/pesticides/','ZM-R07',None,'سموم و حفاظت گیاه'),
 ('/agriculture/genetics/','ZM-R08',None,'صفحه ژنتیک و اصلاح نژاد'),
 ('/agriculture/water-soil/','ZM-R09',None,'راهنمای آب و خاک'),
 ('/weather/','ZM-R09',None,'هواشناسی'),
 ('/agriculture/machinery/','ZM-R10',None,'راهنمای ماشین‌آلات کشاورزی'),
 ('/agriculture/tools/','ZM-R10',None,'ادوات کشاورزی'),
 ('/agriculture/gardening-tools/','ZM-R10',None,'ادوات باغبانی'),
 ('/industry/','ZM-R11',None,'صفحه صنعت و فرآوری'),
 ('/research/','ZM-R12','applied-research',None),
 ('/knowledge/','ZM-R12','knowledge-management',None),
 ('/agents/','ZM-R13','ai-assistants',None),
 ('/business/','ZM-R13','management-dashboard',None),
 ('/amozeshgah/','ZM-R14','zomorod-academy',None),
 ('/services/','ZM-R15',None,'خدمات شرکت'),
 ('/economy/','ZM-R15',None,'اقتصاد'),
 ('/market/','ZM-R15',None,'بازار'),
 ('/agriculture/market/','ZM-R15',None,'بازار محصولات کشاورزی'),
 ('/agriculture/offices/','ZM-R15',None,'ادارات و خدمات کشاورزی'),
 ('/mohammad/','ZM-R20','general-contracting',None),
 ('/tala/','ZM-R22',None,'طلا و جواهر زمرد ملل'),
 ('/ghanadi/','ZM-R24','pastry-confectionery',None),
 ('/studio/','ZM-R25',None,'استودیو'),
 ('/company/','ZM-R16','about-company',None),
 ('/about/','ZM-R16',None,'درباره ما'),
 ('/contact/','ZM-R16','contact-us',None),
 ('/blog/','ZM-R16',None,'وبلاگ'),
 ('/zm-specialist-library-2026.html','ZM-R16','articles-encyclopedia',None),
 ('/news/','ZM-R17','latest',None),
]
assert len(ROUTES)==len({r[0] for r in ROUTES})
EXISTING_COUNT=520

def new_image(rid,title,slug):
    seed=int(hashlib.sha256(f'{rid}:{slug}:v9'.encode()).hexdigest()[:10],16)
    shade=17+seed%41
    x=118+seed%205
    yy=100+seed%46
    g1=f'hsl({shade+78} 34% 28%)'
    g2=f'hsl({shade+73} 34% 16%)'
    # Explicitly illustrative, never pretending to be photographs.
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 320"><defs><linearGradient id="bg" x2=".9" y2="1"><stop stop-color="{g1}"/><stop offset="1" stop-color="{g2}"/></linearGradient></defs><rect width="560" height="320" fill="url(#bg)"/><circle cx="{x}" cy="{yy}" r="112" fill="#e2cb88" opacity=".17"/><path d="M63 190L187 93l112 98 96-75 112 86V279H63Z" fill="#e6d7b1" opacity=".65"/><path d="M85 272H475" stroke="#d5a948" stroke-width="9" stroke-linecap="round"/><circle cx="265" cy="168" r="68" fill="#28583a" stroke="#e7c46b" stroke-width="9"/><path d="M236 168l22 25 45-57" stroke="#f5e1a0" fill="none" stroke-width="12" stroke-linejoin="round" stroke-linecap="round"/><circle cx="{430+seed%25}" cy="{50+seed%30}" r="{13+seed%7}" fill="#ffd474" opacity=".75"/></svg>'''
    return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()

def norm(s):return re.sub(r'[^\w\u0600-\u06ff]+','',s.replace('ي','ی').replace('ك','ک').replace('\u200c','').casefold())

def patch(source):
    if VERSION in source:raise ValueError('V9 already deployed; refuse repeated operation')
    m=re.search(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)',source,re.S)
    if not m:raise ValueError('Missing V8 data')
    data=json.loads(m.group(2));rows=data['rows'];
    if len(rows)!=26 or sum(len(r['cards']) for r in rows)!=EXISTING_COUNT:
        raise ValueError('Expected exactly 26 existing shelves and 520 original cards')
    rowmap={r['id']:r for r in rows}; assert len(rowmap)==26
    assert rows[-2]['title']=='شرکت، رسانه و ارتباطات' and rows[-1]['title']=='اخبار شرکت'
    assert all(len(r['cards'])==20 for r in rows)
    current_names={norm(c['title']) for r in rows for c in r['cards']}
    mapped=[]; newcards=[]
    for path,rid,slug,title in ROUTES:
        assert path.startswith('/') and not path.startswith('//') and '\\' not in path
        row=rowmap[rid]
        existing=next((c for c in row['cards'] if c.get('slug')==slug),None) if slug else None
        if slug and not existing:raise ValueError('Existing card missing: '+rid+':'+slug)
        if not existing:
            assert title is not None
            if norm(title) in current_names:raise ValueError('Card already exists: '+title)
            current_names.add(norm(title))
            newslug='live-'+hashlib.sha256(path.encode()).hexdigest()[:14]
            existing=dict(id=rid+'-LIVE-'+newslug,title=title,slug=newslug,
                          image=new_image(rid,title,newslug),imageStatus='distinct_vector_illustration',
                          canonicalUrl=path,livePage=True)
            row['cards'].append(existing)
            newcards.append((path,rid,title))
        else:
            if existing.get('canonicalUrl') not in (None,path):raise ValueError('Conflicting old URL')
            existing['canonicalUrl']=path
            existing['livePage']=True
        mapped.append((path,rid,existing['title']))
    # A category for every real route was found. Never manufacture an unnecessary row.
    # The previous 520 cards remain in their original sequence; real routes are appended only if not present.
    data['version']='homepage-v9-live-routes'
    data['liveRouteMapCount']=len(mapped)
    data['liveRouteNewCardCount']=len(newcards)
    result=source[:m.start(2)]+json.dumps(data,ensure_ascii=False,separators=(',',':'))+source[m.end(2):]
    before="config.rows?.length!==26 || config.rows.some(r=>r.cards?.length!==20)"
    after="config.rows?.length!==26 || config.rows.some(r=>r.cards?.length<20)"
    if result.count(before)!=1:raise ValueError('JS row-card guard mismatch')
    result=result.replace(before,after,1)
    old="const a=el('a',{className:'topic-card',href:dest,'aria-label':`مشاهده ${topic.title}`});"
    new="const a=el('a',{className:'topic-card',href:topic.canonicalUrl||dest,'aria-label':`مشاهده ${topic.title}`});"
    if result.count(old)!=1:raise ValueError('Card link builder mismatch')
    result=result.replace(old,new,1)
    # Preserve all 17 orbit satellite links; add no unused row, as every page has a related shelf.
    result=result.replace('</body>',f'<!-- {VERSION} -->\n</body>',1)
    return result,mapped,newcards

def verify(original,edited,mapped,newcards):
    def get(s):return json.loads(re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',s,re.S).group(1))['rows']
    old,new=get(original),get(edited)
    assert len(new)==len(old)==26
    assert sum(len(r['cards']) for r in old)==520
    assert sum(len(r['cards']) for r in new)==520+len(newcards)
    assert [x['title'] for x in new]==[x['title'] for x in old]
    assert [x['id'] for x in new]==[x['id'] for x in old]
    for a,b in zip(old,new):
        assert len(b['cards'])>=len(a['cards'])
        for c,d in zip(a['cards'],b['cards']):
            assert c['id']==d['id'] and c['title']==d['title'] and c['slug']==d['slug']
            assert c['image']==d['image']
    allroutes=[c['canonicalUrl'] for r in new for c in r['cards'] if c.get('canonicalUrl')]
    assert len(allroutes)==len(set(allroutes))==len(mapped)
    assert len([r for r in new if r['index']<=17])==17
    assert new[-2]['title']=='شرکت، رسانه و ارتباطات'
    assert 'topic.canonicalUrl||dest' in edited
    assert 'زمرد ملل محفوظ است . آبان ۱۳۹۸ مجتبی روزگار' in edited
    assert edited.count('src="/static/site/zomorod-v7/company-logo.webp"')==1
    print(f'V9_VALIDATED=26 rows; {len(allroutes)} unique real page links; {len(newcards)} added cards; {520+len(newcards)} total cards; no old card removed')
    print('V9_LINKS='+json.dumps(mapped,ensure_ascii=False))
    print('V9_NEW_CARDS='+json.dumps(newcards,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True)
    x=p.parse_args();o=x.source.read_text(encoding='utf-8');out,mapped,newcards=patch(o);verify(o,out,mapped,newcards)
    if x.output.exists():raise ValueError('Refuse overwrite of preexisting candidate: '+str(x.output))
    x.output.write_text(out,encoding='utf-8')
    print('V9_CANDIDATE_PATH='+str(x.output))

if __name__=='__main__':main()