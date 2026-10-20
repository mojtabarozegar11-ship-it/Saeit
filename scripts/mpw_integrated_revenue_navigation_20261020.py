#!/usr/bin/env python3
"""Main MojPlayWin only: one canonical menu with twelve actual revenue links, atomically."""
from pathlib import Path
import hashlib,json,os,re,stat,sys,tempfile
ROOT=Path('/home/zomorod2/mojplaywin.com')
HOME=ROOT/'design-preview-20261017/production-home-20261017.html'
FOLDER=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages'
NAMES=('about-mojtaba-rozegar','about','agents','company','economy','industry','knowledge','market','research','services','studio','ventures-agriculture','ventures-cafe-restaurant','ventures-carpets','ventures-currency-crypto','ventures-ecommerce','ventures-fuel-station','ventures-hospitality','ventures-jewelry-gold')
SLUGS=('website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care')
LABELS=('Website Doctor','Landing Page Studio','AI Workflow Automation','Business Spreadsheets','Website Templates','Social Media Kits','Resume Builder','Logo & Brand Studio','Browser Games','Marketing Workspace','Business Calculators','Website Care')
MARK='data-mpw-revenue-nav-20261020="true"'
HEADER=re.compile(r'<header\b[^>]*class=["\x27]mw-site-nav["\x27][^>]*>[\s\S]*?</header\s*>',re.I)
def fail(s):raise RuntimeError(s)
def digest(b):return hashlib.sha256(b).hexdigest()
def paths():return [HOME]+[FOLDER/(n+'.html') for n in NAMES]
def guard():
    if ROOT.resolve()!=ROOT or ROOT.is_symlink() or not ROOT.is_dir():fail('Unexpected main site')
    if not FOLDER.is_dir() or FOLDER.is_symlink() or not (ROOT/'.htaccess').is_file():fail('Main published routing missing')
    ht=(ROOT/'.htaccess').read_text('utf8','replace')
    if 'production-home-20261017.html' not in ht or '_mpw_dynamic_main_shell_20261019.php' not in ht:fail('Main site route identity changed')
    for p in paths():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():fail('Unverified page '+str(p))
    for slug in SLUGS:
        p=ROOT/'mpw-editorial/revenue'/slug/'index.html'
        if not p.is_file() or p.is_symlink():fail('Revenue tool page not live locally: '+slug)
def new_menu(header):
    if MARK in header:fail('Already patched')
    if header.count('id="mw-all-pages-menu"')!=1 or header.count('aria-label="Primary MojPlayWin navigation"')!=1:fail('Unexpected canonical menu structure')
    anchor='<a href="/services/">Services</a>'
    if header.count(anchor)!=1:fail('Missing Services top-nav link')
    header=header.replace(anchor,anchor+'\n    <a href="/mpw-editorial/revenue/index.html" '+MARK+'>12 Revenue Tools</a>',1)
    needle='<section><h3>Company & support</h3>'
    if header.count(needle)!=1:fail('Mega menu company block missing')
    hrefs=''.join('<a href="/mpw-editorial/revenue/'+s+'/index.html">'+v+'</a>' for s,v in zip(SLUGS,LABELS))
    section='<section data-mpw-earning-directory="v1"><h3>Earn & create · 12 tools</h3><a href="/mpw-editorial/revenue/index.html">Explore all 12 opportunities</a>'+hrefs+'</section>\n        '
    header=header.replace(needle,section+needle,1)
    if header.count(MARK)!=1 or header.count('data-mpw-earning-directory="v1"')!=1:fail('Bad menu insertion')
    for slug in SLUGS:
        if header.count('/mpw-editorial/revenue/'+slug+'/index.html')!=1:fail('Missing one menu offer')
    return header
def patch(doc,header):
    text=doc.decode('utf8')
    blocks=list(HEADER.finditer(text))
    if len(blocks)!=1:fail('Page header mismatch')
    before=blocks[0].group(0)
    if MARK in text:fail('Menu already patched')
    if 'mw-site-nav' not in before or 'mw-nav-panel' not in before:fail('Cannot safely unify this page')
    after=text[:blocks[0].start()]+header+text[blocks[0].end():]
    if after.count(MARK)!=1 or after.count('</header>')!=text.count('</header>'):fail('Header replacement differs structurally')
    for mark in ('<main','<footer'):
        if after.count(mark)!=text.count(mark):fail('Body or footer changed')
    return after.encode('utf8')
def atomic(path,bytes_):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.mpw-menu-staging-')
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,'wb') as f:f.write(bytes_);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def backup(run):
    if not re.fullmatch(r'\d{8,20}',run):fail('Invalid release')
    return ROOT.parent/('.mpw-menu-integrated-'+run)
def publish(run):
    guard()
    sources={str(p.relative_to(ROOT)):p.read_bytes() for p in paths()}
    home=sources[str(HOME.relative_to(ROOT))].decode('utf8')
    blocks=list(HEADER.finditer(home))
    if len(blocks)!=1:fail('Unrecognized homepage nav')
    h=new_menu(blocks[0].group(0))
    newer={key:patch(raw,h) for key,raw in sources.items()}
    if len(newer)!=20:fail('Expect 20 main pages')
    b=backup(run)
    if b.exists() or b.is_symlink():fail('Backup collision')
    b.mkdir(mode=0o700)
    files={}
    for key,old in sources.items():
        idx=str(len(files))+'-original'
        out=b/idx
        with out.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old)
        files[key]={'backup':idx,'before':digest(old),'after':digest(newer[key])}
    (b/'manifest.json').write_text(json.dumps({'run':run,'files':files},sort_keys=True))
    os.chmod(b/'manifest.json',0o600)
    changed=[]
    try:
        for key in sorted(newer):
            p=ROOT/key
            if digest(p.read_bytes())!=files[key]['before']:fail('Concurrent content edit')
            atomic(p,newer[key]);changed.append(key)
            if digest(p.read_bytes())!=files[key]['after']:fail('Mismatch after update')
    except BaseException:
        for key in reversed(changed):
            p=ROOT/key
            if digest(p.read_bytes())==files[key]['after']:atomic(p,sources[key])
        raise
    print('MPW_MENU_20_MAIN_PAGES_PUBLISHED='+json.dumps({'pages':len(changed),'offer_links':12,'home_and_editorials_only':True,'payment_and_child_app_untouched':True}))
def rollback(run):
    guard();b=backup(run)
    if not b.is_dir() or b.is_symlink():fail('No saved main-page backups')
    meta=json.loads((b/'manifest.json').read_text())
    if meta.get('run')!=run or len(meta['files'])!=20:fail('Backup identity invalid')
    saved={}
    for key,data in meta['files'].items():
        p=ROOT/key;q=b/data['backup']
        if not p.is_file() or p.is_symlink() or not q.is_file() or q.is_symlink() or digest(q.read_bytes())!=data['before']:fail('Backup mismatch')
        if digest(p.read_bytes())!=data['after']:fail('Concurrent site modifications; refuse destructive restore')
        saved[key]=q.read_bytes()
    for key,contents in saved.items():atomic(ROOT/key,contents)
    if any(digest((ROOT/key).read_bytes())!=digest(data) for key,data in saved.items()):fail('Restore mismatch')
    print('MPW_MAIN_MENU_ROLLBACK=PASS')
def selftest():
    sample='<header class="mw-site-nav"><nav aria-label="Primary MojPlayWin navigation"><a href="/services/">Services</a><details id="mw-all-pages-menu"><div class="mw-nav-panel"><section><h3>Company & support</h3></section></div></details></nav></header>'
    h=new_menu(sample)
    raw=('<html><body>'+sample+'<main>KEEP</main><footer>KEEP</footer></body></html>').encode()
    out=patch(raw,h)
    assert out.count(b'data-mpw-earning-directory="v1"')==1 and b'<main>KEEP</main>' in out
    print('MPW_MENU_20_PAGE_BOUNDED_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):(publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('selftest|publish RUN_ID|rollback RUN_ID')
