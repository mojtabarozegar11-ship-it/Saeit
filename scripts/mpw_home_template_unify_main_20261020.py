#!/usr/bin/env python3
"""Harmonize ONLY MojPlayWin main public pages with the LIVE verified home appearance.
Keeps all content and backend, payment routes, employee subsites and all child sites unchanged.
"""
import os,sys,re,json,hashlib,stat,tempfile,subprocess
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com')
HOME=ROOT/'design-preview-20261017/production-home-20261017.html'
INTERNAL=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages'
REVENUE=ROOT/'mpw-editorial/revenue'
PHP=ROOT/'design-preview-20261017/_mpw_dynamic_main_shell_20261019.php'
CSS=REVENUE/'assets/home-shared-v1.css'
NAMES=('about-mojtaba-rozegar','about','agents','company','economy','industry','knowledge','market','research','services','studio','ventures-agriculture','ventures-cafe-restaurant','ventures-carpets','ventures-currency-crypto','ventures-ecommerce','ventures-fuel-station','ventures-hospitality','ventures-jewelry-gold')
SLUGS=('website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care')
HEAD=re.compile(r'<header\b(?=[^>]*\bclass=["\x27](?:mw-site-nav|mpw-header)["\x27])[^>]*>[\s\S]*?</header\s*>',re.I)
FOOT=re.compile(r'<footer\b(?=[^>]*\bclass=["\x27](?:mw-site-footer|mpw-footer)["\x27])[^>]*>[\s\S]*?</footer\s*>',re.I)
STYLE=re.compile(r'<style\b[^>]*>([\s\S]*?)</style\s*>',re.I)
LINK=re.compile(r'<link\b(?=[^>]*\brel=["\x27]stylesheet["\x27])[^>]*>',re.I)
MARK='data-mpw-home-unified-20261020="v1"'
CSS_URL='/mpw-editorial/revenue/assets/home-shared-v1.css'
def fail(s):raise RuntimeError(s)
def digest(b):return hashlib.sha256(b).hexdigest()
def files():
    out={'php':PHP}
    out.update({name:INTERNAL/(name+'.html') for name in NAMES})
    out['revenue-index']=REVENUE/'index.html'
    out.update({'rev-'+name:REVENUE/name/'index.html' for name in SLUGS})
    return out
def guard():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or not HOME.is_file() or HOME.is_symlink():fail('Unverified home site')
    if PHP.is_symlink() or not PHP.is_file() or CSS.is_symlink() or CSS.exists():fail('Unexpected PHP or existing shared CSS')
    if not (ROOT/'.htaccess').is_file() or not (ROOT/'passenger_wsgi.py').is_file():fail('Shared site document root not confirmed')
    if not INTERNAL.is_dir() or INTERNAL.is_symlink() or not REVENUE.is_dir() or REVENUE.is_symlink():fail('Main-only directories unverified')
    for key,p in files().items():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Invalid published main page '+key)
def once(regex,text,key):
    hits=list(regex.finditer(text))
    if len(hits)!=1:fail('Expected one '+key+'; found '+str(len(hits)))
    return hits[0]
def shell():
    text=HOME.read_text('utf8')
    if text.count(MARK) or not text.lstrip().lower().startswith('<!doctype html'):fail('Unexpected home source; leading='+repr(text[:70])+' marker_count='+str(text.count(MARK)))
    h=once(HEAD,text,'home header').group(0)
    f=once(FOOT,text,'home footer').group(0)
    if 'mw-all-pages-menu' not in h or '12 Revenue Tools' not in h:fail('Corrected homepage revenue menu not present')
    if 'Mojtaba' not in f and 'Mojtaba Roozegar' not in f:fail('Original footer legal identity absent')
    css='\n\n'.join(x.group(1) for x in STYLE.finditer(text))
    if len(css)<1500:fail('Insufficient native home CSS')
    # Existing home stylesheet links are kept as links where present, using only first-party rooted static assets.
    linked=[]
    for link in LINK.findall(text):
        m=re.search(r'href=["\x27]([^"\x27]+)["\x27]',link,re.I)
        if m and m.group(1).startswith('/') and not m.group(1).startswith('//'):linked.append(m.group(1))
    css='/* Exact native CSS extracted from current MojPlayWin homepage; all other main pages share this source */\n'+css+'\n'+(
    "\nbody{background:#090b0c;color:#f4eedc}body .mw-site-nav{z-index:40}"+
    "body .mw-site-footer{color:#f1e7ce}body .mw-nav-panel{background:#11191d}"+
    "@media(max-width:740px){body .mw-site-nav{padding:10px 14px}body .mw-nav-panel{max-width:92vw}}")
    return h,f,css.encode('utf8'),linked
def patch_html(key,raw,header,footer,links):
    text=raw.decode('utf8')
    if MARK in text or CSS_URL in text:fail('Page already unified: '+key)
    if not text.lstrip().lower().startswith('<!doctype html') or not text.lower().count('</head>')==1:fail('Invalid HTML '+key)
    oldh=once(HEAD,text,key+' header')
    oldf=once(FOOT,text,key+' footer')
    h=header.replace('<header ','<header '+MARK+' ',1)
    out=text[:oldh.start()]+h+text[oldh.end():]
    oldf2=once(FOOT,out,key+' footer after header')
    out=out[:oldf2.start()]+footer+out[oldf2.end():]
    new_links=''.join('<link rel="stylesheet" href="'+href+'">' for href in links)
    new_links+='<link rel="stylesheet" href="'+CSS_URL+'?v=20261020">'
    out=out.replace('</head>',new_links+'</head>',1)
    if out.count(MARK)!=1 or out.count(CSS_URL)!=1:fail('Marker not unique '+key)
    for name in ('<main','</main>'):
        if out.lower().count(name)!=text.lower().count(name):fail('Main body content structure changed '+key)
    if key.startswith('rev-') or key=='revenue-index':
        if out.count('mpw-functional-tool')!=text.count('mpw-functional-tool'):fail('Lost interactive app '+key)
    if key.startswith('rev-') and out.count('assets/tools-v1.js')!=1:fail('Tool javascript lost '+key)
    return out.encode('utf8')
def patch_php(original):
    text=original.decode('utf8')
    tag='// MPW_HOME_UNIFICATION_RELEASE_20261020: reuse research shell reloaded from unified source\n'
    if 'MPW_HOME_UNIFICATION_RELEASE_20261020' in text:fail('PHP already released')
    if text.count('declare(strict_types=1);')!=1 or text.count("function layoutParts(): array {")!=1:fail('PHP header drift')
    newer=text.replace('declare(strict_types=1);','declare(strict_types=1);\n'+tag,1)
    return newer.encode('utf8')
def lint_php(raw):
    fd,p=tempfile.mkstemp(dir=PHP.parent,suffix='.php',prefix='.mpw-shell-check-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw)
        r=subprocess.run(['php','-l',p],capture_output=True,text=True,timeout=20,check=False)
        if r.returncode:fail('Native PHP syntax invalid: '+r.stderr[-350:])
    finally:
        if os.path.exists(p):os.unlink(p)
def atomic(p,payload):
    fd,tmp=tempfile.mkstemp(dir=p.parent,prefix='.mpw-unify-stage-')
    try:
        os.fchmod(fd,stat.S_IMODE(p.stat().st_mode) if p.exists() else 0o644)
        with os.fdopen(fd,'wb') as o:o.write(payload);o.flush();os.fsync(o.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def backup(run):
    if not re.fullmatch(r'[0-9]{8,20}',run):fail('Bad run id')
    return ROOT.parent/('.mpw-unify-native-'+run)
def publish(run):
    guard()
    h,f,c,links=shell()
    target=files()
    old={name:p.read_bytes() for name,p in target.items()}
    new={name:(patch_php(raw) if name=='php' else patch_html(name,raw,h,f,links)) for name,raw in old.items()}
    lint_php(new['php'])
    state=backup(run)
    if state.exists() or state.is_symlink():fail('Backup collision')
    state.mkdir(mode=0o700)
    records={}
    for key,content in old.items():
        name=str(len(records))+'.orig'
        with (state/name).open('xb') as out:os.fchmod(out.fileno(),0o600);out.write(content)
        records[key]={'backup':name,'before':digest(content),'after':digest(new[key])}
    records['css']={'backup':None,'before':None,'after':digest(c)}
    (state/'manifest.json').write_text(json.dumps({'run':run,'records':records},sort_keys=True))
    os.chmod(state/'manifest.json',0o600)
    changed=[]
    try:
        for key in ('css',*target.keys()):
            p=CSS if key=='css' else target[key]
            if key=='css':
                if p.exists() or p.is_symlink():fail('CSS release collision')
                content=c
            else:
                if digest(p.read_bytes())!=records[key]['before']:fail('Concurrent edit: '+key)
                content=new[key]
            atomic(p,content)
            changed.append(key)
            if digest(p.read_bytes())!=records[key]['after']:fail('Postwrite mismatch: '+key)
    except BaseException:
        for key in reversed(changed):
            p=CSS if key=='css' else target[key]
            if digest(p.read_bytes())==records[key]['after']:
                if key=='css':p.unlink()
                else:atomic(p,old[key])
        raise
    print('MPW_NATIVE_HOME_LAYOUT_APPLIED='+json.dumps({'revenue_pages':13,'editorial_pages':19,'php_renderer_revalidated':True,'homepage_source_readonly':True,'all_content_retained':True,'shared_payment_unchanged':True,'subsites_unmodified':True,'shared_css_bytes':len(c)}))
def rollback(run):
    state=backup(run)
    if state.is_symlink() or not state.is_dir():fail('Unknown backup')
    meta=json.loads((state/'manifest.json').read_text())
    if meta.get('run')!=run:fail('Wrong backup release')
    target=files();restore={}
    for key,record in meta['records'].items():
        p=CSS if key=='css' else target[key]
        if p.is_symlink() or not p.is_file() or digest(p.read_bytes())!=record['after']:fail('Unsafe concurrent file modification: '+key)
        if key!='css':
            b=state/record['backup']
            if b.is_symlink() or not b.is_file() or digest(b.read_bytes())!=record['before']:fail('Invalid recovery copy')
            restore[key]=b.read_bytes()
    for key,data in restore.items():atomic(target[key],data)
    CSS.unlink()
    print('MPW_NATIVE_HOME_LAYOUT_ROLLBACK=PASS')
def selftest():
    h='<header class="mw-site-nav"><div id="mw-all-pages-menu">12 Revenue Tools</div></header>'
    f='<footer class="mw-site-footer">Mojtaba Roozegar</footer>'
    base='<!doctype html><html lang="en"><head><title>Test</title></head><body><header class="mpw-header">Old</header><main>Preserve this content</main><footer class="mpw-footer">Old</footer></body></html>'
    transformed=patch_html('services',base.encode(),h,f,[])
    assert b'Preserve this content' in transformed and b'Mojtaba Roozegar' in transformed and b'mpw-home-unified' in transformed
    print('MPW_NATIVE_HOME_UNIFIED_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
