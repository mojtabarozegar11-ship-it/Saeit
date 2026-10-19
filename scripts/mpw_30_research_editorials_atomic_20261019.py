#!/usr/bin/env python3
"""MojPlayWin main: append 30 independent research briefs to 19 existing informational HTML assets.

NO shared Django/Passenger restart or .htaccess write. No store/payment/admin/child-site writes.
Production changes are checked, snapshotted, reversible, and limited to 19 pinned files.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import hashlib,html,json,os,re,stat,sys,tempfile,fcntl

ROOT=Path('/home/zomorod2/mojplaywin.com')
STATIC=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages'
HTACCESS=ROOT/'.htaccess'
ROUTES=(
 '/company/','/research/','/knowledge/','/industry/','/economy/','/studio/',
 '/market/','/agents/','/ventures/agriculture/','/ventures/cafe-restaurant/',
 '/ventures/fuel-station/','/ventures/jewelry-gold/','/ventures/carpets/',
 '/ventures/currency-crypto/','/ventures/ecommerce/','/ventures/hospitality/',
 '/services/','/about/','/about/mojtaba-rozegar/',
)
MARK='MPW_RESEARCH_EDITORIALS_30_20261019'
CLS='mpw-research-brief-20261019'
PUBLICBASE='/design-preview-20261017/mpw-ten-editorials-20261018/pages/'
EXCLUDED=('/store/','/checkout/','/payment/','/admin/','/api/','/farnaz/','/saman/',
          '/picm/','/taniya/','/zahra/','/mojtaba.roozegar/')
STYLE='''<style id="mpw-research30-style-20261019">
.mpw-research30{margin:clamp(2rem,5vw,5rem) auto;max-width:1240px;padding:clamp(1rem,2.5vw,2.1rem);color:#f4efe5;background:linear-gradient(140deg,#141916,#241c10 54%,#0f1616);border:1px solid #cda965;border-radius:22px;box-shadow:0 18px 56px #0006;box-sizing:border-box;isolation:isolate}
.mpw-research30 *{box-sizing:border-box}.mpw-research30 .mpw-r30-eyebrow{font-size:.82rem;font-weight:700;color:#e7c57b;letter-spacing:.1em;text-transform:uppercase}
.mpw-research30 h2{font-size:clamp(1.55rem,3.1vw,2.5rem);line-height:1.22;color:#ffdf99;margin:.5rem 0 1rem}
.mpw-research30 .mpw-r30-intro{line-height:1.75;color:#e9e1d3;max-width:90ch}
.mpw-research30 .mpw-r30-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:1.2rem;margin-top:1.4rem}
.mpw-research30 .mpw-r30-paper{min-width:0;padding:clamp(1rem,2.2vw,1.7rem);border:1px solid #af8e57;background:#101615;border-radius:16px;box-shadow:0 12px 28px #0004}
.mpw-research30 .mpw-r30-tag{font-size:.79rem;color:#e5bc70;letter-spacing:.09em;font-weight:750}.mpw-research30 h3{font-size:clamp(1.1rem,1.65vw,1.4rem);line-height:1.33;color:#ffe4ac;margin:.65rem 0 1rem}
.mpw-research30 h4{font-size:1rem;color:#f3d292;margin:1.2rem 0 .3rem}.mpw-research30 p,.mpw-research30 li{font-size:.95rem;line-height:1.82;color:#eee7dd;overflow-wrap:anywhere}
.mpw-research30 a{color:#f5cb76;text-decoration:underline;text-underline-offset:3px}.mpw-research30 a:hover,.mpw-research30 a:focus{color:#fff3cc}
.mpw-research30 .mpw-r30-references{border-top:1px solid #665439;margin-top:1rem;padding-top:.55rem}.mpw-research30 .mpw-r30-references ul{padding-inline-start:1.3rem}
.mpw-research30 .mpw-r30-note{border-inline-start:3px solid #dcb66c;background:#ffffff0c;padding:.8rem 1rem;line-height:1.7;color:#d7cbbc;margin-top:1.5rem}
@media(max-width:600px){.mpw-research30{padding:12px;border-radius:14px}.mpw-research30 .mpw-r30-paper{padding:14px}}
@media(prefers-reduced-motion:reduce){.mpw-research30 *{transition:none!important;animation:none!important}}
</style>'''

def sha(b):return hashlib.sha256(b).hexdigest()
def fail(msg):raise RuntimeError(msg)
def slug(route):return '-'.join(x for x in route.strip('/').split('/') if x)
def page(route):return STATIC/(slug(route)+'.html')
def safety_roots():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT:fail('Unexpected docroot')
    if not STATIC.is_dir() or STATIC.is_symlink():fail('Missing isolated static folder')
    if not HTACCESS.is_file() or HTACCESS.is_symlink():fail('Routing file unsafe')
    txt=HTACCESS.read_text('utf-8',errors='replace')
    for route in ROUTES:
        if route.startswith(EXCLUDED):fail('Protected route selected '+route)
        # Each URL remains owned by the already-public whitelist. No rewriting here.
        cond='RewriteCond %{REQUEST_URI} ^'+re.escape(route).replace('\\/','/')+'$'
        expected='/design-preview-20261017/mpw-ten-editorials-20261018/pages/'+slug(route)+'.html'
        if cond not in txt or expected not in txt:fail('Unexpected live route ownership: '+route)
    if len(ROUTES)!=19 or len(set(ROUTES))!=19:fail('Invalid target whitelist')

def validate_source(data):
    if data.get('collection')!='MojPlayWin research-grade editorial briefs':fail('Invalid dataset identity')
    if len(data.get('articles',[]))!=30:fail('Require exactly thirty articles')
    if set(a['route'] for a in data['articles'])!=set(ROUTES):fail('Missing target routes')
    if len({a['title'].casefold() for a in data['articles']})!=30:fail('Duplicate title')
    sources=data.get('sources',{})
    for a in data['articles']:
        if any(len(a[k].split())<n for k,n in (('question',12),('method',30),('analysis',30),('assessment',20),('limitations',12))):fail('Insufficient scientific detail in '+a['title'])
        if not a['refs'] or any(x not in sources for x in a['refs']):fail('Missing source')
    if not 10<=len(sources)<=25:fail('Unexpected reference registry')
    return data

def render(data,route):
    docs=[a for a in data['articles'] if a['route']==route]
    assert len(docs) in (1,2)
    pieces=[f'<!-- {MARK}_BEGIN {html.escape(route)} -->',STYLE,
        f'<section class="mpw-research30" id="mpw-research-editorials-20261019-{slug(route)}" aria-labelledby="mpw-research30-title-{slug(route)}">',
        '<p class="mpw-r30-eyebrow">MojPlayWin | Advanced research and professional methodology</p>',
        f'<h2 id="mpw-research30-title-{slug(route)}">Research-grade insights for {html.escape(route.strip("/").replace("/"," / ").replace("-"," ").title())}</h2>',
        '<p class="mpw-r30-intro">Independent technical analyses with explicit research questions, proposed methods, measurable outcomes, limitations and sources. These are educational proposals, not peer-reviewed original experiments, accredited findings, or evidence that any described facility is operating.</p>',
        '<div class="mpw-r30-grid">']
    for a in docs:
        idx=data['articles'].index(a)+1
        pieces += [f'<article class="mpw-r30-paper {CLS}" id="mpw-research-brief-{idx:02d}">',
            f'<span class="mpw-r30-tag">RESEARCH BRIEF {idx:02d} / 30</span>',
            f'<h3>{html.escape(a["title"])}</h3>',
            '<h4>Research question</h4>',f'<p>{html.escape(a["question"])}</p>',
            '<h4>Proposed research protocol</h4>',f'<p>{html.escape(a["method"])}</p>',
            '<h4>Analytical framework and study design</h4>',f'<p>{html.escape(a["analysis"])}</p>',
            '<h4>Validation, reporting and acceptance evidence</h4>',f'<p>{html.escape(a["assessment"])}</p>',
            '<h4>Limitations and responsible interpretation</h4>',f'<p>{html.escape(a["limitations"])}</p>',
            '<div class="mpw-r30-references"><h4>Methodological references</h4><ul>']
        for ref in a['refs']:
            name,url=data['sources'][ref]
            if not url.startswith('https://'):fail('Non-HTTPS source URL')
            pieces.append(f'<li><a href="{html.escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(name)}</a></li>')
        pieces += ['</ul></div></article>']
    pieces += ['</div>','<p class="mpw-r30-note"><strong>Evidence notice:</strong> Methodology guides cite external benchmarks but do not claim peer review, professional licensing, regulatory approval, guaranteed results or that examples describe an active MojPlayWin product. Verify applicability, local law and newer editions before real-world decisions.</p>','</section>',f'<!-- {MARK}_END {html.escape(route)} -->']
    return '\n'.join(pieces)

def check_page(route,raw):
    if not (2000<len(raw)<1700000):fail('Page size outside trusted bounds '+route)
    doc=raw.decode('utf-8')
    if MARK in doc:fail('Already published; do not duplicate '+route)
    if len(re.findall(r'<main\b',doc,re.I))!=1 or len(re.findall(r'</main\s*>',doc,re.I))!=1 or len(re.findall(r'<h1\b',doc,re.I))!=1:fail('Semantic main/h1 mismatch '+route)
    if doc.count('class="mpw-ten-card"')!=10 or doc.count('id="mpw-ten-illustrated-20261018"')!=1:fail('Baseline 10 notes missing '+route)
    if route=='/about/':
        for mark,count in [('id="mpw-founder-spotlight-20261019"',1),('id="mpw-meet-team-20261018"',1),('id="mpw-senior-advisory-20261018"',1),('id="mpw-international-team-20261018"',1),('id="mpw-seven-gallery-20261019"',1),('class="mpw-team-card"',10),('class="mpw-advisory-card"',10),('class="mpw-intl-card"',10)]:
            if doc.count(mark)!=count:fail('Critical About marker changed: '+mark)
    return doc

def combine(route,raw,data):
    doc=check_page(route,raw)
    addition='\n'+render(data,route)+'\n'
    matches=list(re.finditer(r'</main\s*>',doc,re.I))
    pos=matches[0].start()
    out=doc[:pos]+addition+doc[pos:]
    if out.replace(addition,'',1)!=doc:fail('Not byte reversible '+route)
    if out.count(CLS)!=len([a for a in data['articles'] if a['route']==route]):fail('Brief count mismatch '+route)
    if out.count(MARK+'_BEGIN')!=1:fail('Marker duplication '+route)
    if len(out.encode('utf-8'))>=1950000:fail('HTML too large '+route)
    return out.encode('utf-8')

def atomic(path,b,mode):
    if path.is_symlink():fail('Symlink forbidden')
    fd,temp=tempfile.mkstemp(prefix='.mpw-r30-',dir=str(path.parent))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def private_paths(run):
    if not re.fullmatch('[0-9]{9,20}',run):fail('Unsafe run id')
    return (ROOT.parent/f'.mpw-30-scientific-content-{run}.json', ROOT.parent/f'.mpw-30-scientific-backup-{run}')

def write_json(path,value):
    with open(path,'x',encoding='utf-8') as f:
        os.chmod(path,0o600);json.dump(value,f,ensure_ascii=False,sort_keys=True);f.flush();os.fsync(f.fileno())

def install(run,digest):
    stage,backup=private_paths(run)
    if not re.fullmatch('[a-f0-9]{64}',digest):fail('Invalid expected source sha')
    if not stage.is_file() or stage.is_symlink() or sha(stage.read_bytes())!=digest:fail('Staged dataset hash mismatch')
    data=validate_source(json.loads(stage.read_text('utf-8')))
    safety_roots()
    if backup.exists() or backup.is_symlink():fail('Backup location occupied')
    plan={}
    for route in ROUTES:
        p=page(route)
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Unexpected isolated page '+route)
        before=p.read_bytes()
        after=combine(route,before,data)
        plan[route]={'page':p,'before':before,'after':after,'mode':stat.S_IMODE(p.stat().st_mode)}
    backup.mkdir(mode=0o700)
    manifest={'runid':run,'source_sha':digest,'pages':{},'article_count':30,'published':False}
    for route,v in plan.items():
        file=backup/(slug(route)+'.html')
        with open(file,'xb') as f:
            os.chmod(file,0o600);f.write(v['before']);f.flush();os.fsync(f.fileno())
        manifest['pages'][route]={'before':sha(v['before']),'after':sha(v['after']), 'backup':file.name}
    write_json(backup/'manifest.json',manifest)
    touched=[]
    try:
        for route,v in plan.items():
            if sha(v['page'].read_bytes())!=manifest['pages'][route]['before']:fail('Concurrent change before write '+route)
            atomic(v['page'],v['after'],v['mode'])
            touched.append(route)
            if sha(v['page'].read_bytes())!=manifest['pages'][route]['after']:fail('Written hash mismatch '+route)
    except BaseException:
        problems=[]
        for route in reversed(touched):
            v=plan[route]
            if sha(v['page'].read_bytes())==manifest['pages'][route]['after']:
                atomic(v['page'],v['before'],v['mode'])
            elif sha(v['page'].read_bytes())!=manifest['pages'][route]['before']:
                problems.append(route)
        if problems:print('CONCURRENT_EDIT_REFUSE_OVERWRITE='+','.join(problems),file=sys.stderr)
        raise
    print(json.dumps({'status':'MPW_30_RESEARCH_GRADE_ARTICLES_ADDED','pages':19,'articles':30,'other_routes_changed':False,'shared_django_changed':False,'rollback_prepared':True}))

def rollback(run):
    _,backup=private_paths(run)
    if not backup.is_dir() or backup.is_symlink():fail('Backup missing')
    meta=json.loads((backup/'manifest.json').read_text('utf-8'))
    for route,rec in meta['pages'].items():
        p=page(route);current=sha(p.read_bytes())
        if current not in (rec['before'],rec['after']):fail('Concurrent edit; cannot overwrite '+route)
    for route,rec in meta['pages'].items():
        p=page(route);original=(backup/rec['backup']).read_bytes()
        if sha(original)!=rec['before']:fail('Damaged backup '+route)
        if sha(p.read_bytes())==rec['after']:atomic(p,original,stat.S_IMODE(p.stat().st_mode))
    print(json.dumps({'status':'MPW_30_ARTICLES_ROLLED_BACK','restored_paths':19}))

def status(run):
    _,backup=private_paths(run)
    meta=json.loads((backup/'manifest.json').read_text('utf-8'))
    good=[]
    for route,rec in meta['pages'].items():
        p=page(route)
        if p.is_file() and not p.is_symlink() and sha(p.read_bytes())==rec['after']:
            good.append(route)
    print(json.dumps({'status':'MPW_30_ARTICLES_READONLY_STATUS','verified_pages':len(good),'total_expected':19,'articles':30,'all_installed':len(good)==19,'backups_exist':len(list(backup.glob('*.html')))==19}))

if __name__=='__main__':
    if len(sys.argv)<3:fail('Use install RUNID SHA | rollback RUNID | status RUNID')
    action,run=sys.argv[1:3]
    if action=='install' and len(sys.argv)==4:install(run,sys.argv[3])
    elif action=='rollback' and len(sys.argv)==3:rollback(run)
    elif action=='status' and len(sys.argv)==3:status(run)
    else:fail('Invalid mode')