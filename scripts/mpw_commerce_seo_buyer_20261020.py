#!/usr/bin/env python3
"""Bounded, atomic MojPlayWin MAIN-ONLY revenue sitemap and buyer navigation patch.

Does not touch .htaccess, shared Django, Passenger, child sites, payment methods, users or DB.
"""
from __future__ import annotations
import hashlib,json,os,re,stat,subprocess,sys,tempfile
from pathlib import Path
HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
PAGE=ROOT/'mpw-editorial/revenue/index.html'
SITE=ROOT/'design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php'
PAGE_ID='mpw-book-account-steps-20261020'
SITEMAP_ID='MPW_REVENUE_SITEMAP_LINKS_20261020'
SLUGS=('website-doctor','landing-page-studio','ai-automation','business-spreadsheets',
'website-templates','social-media-kits','resume-builder','logo-studio','browser-games',
'marketing-ai','business-calculators','website-care')
ROUTES=('/mpw-editorial/revenue/index.html',)+tuple('/mpw-editorial/revenue/'+slug+'/index.html' for slug in SLUGS)
SNIPPET=(
'<section id="'+PAGE_ID+'" aria-labelledby="mpw-book-guide-title" '
'style="margin-top:34px;padding:24px;border:1px solid #a98b55;background:#182235;border-radius:18px">'
'<p class="eyebrow">HOW TO BUY A VERIFIED DIGITAL BOOK</p>'
'<h2 id="mpw-book-guide-title">Three steps to a secure digital-book purchase</h2>'
'<ol><li><a href="/accounts/register/">Create a customer account</a> '
'or <a href="/accounts/login/">sign in</a> if you already have one.</li>'
'<li>Choose the <a href="/store/product/72/">chess guide (US $7.50)</a> '
'or <a href="/store/product/225/">illustrated story (US $4.00)</a>; '
'open that product&#39;s secure checkout after signing in.</li>'
'<li>Review the individual order invoice before paying; private PDF access '
'is released only after payment has been independently confirmed.</li></ol>'
'<p class="note">Never send funds to a payment address outside your verified '
'order-specific invoice. This guide does not charge you or create an order.</p>'
'</section>\n')
def digest(b):return hashlib.sha256(b).hexdigest()
def fail(msg):raise RuntimeError(msg)
def guard():
    if ROOT.resolve()!=ROOT or ROOT.is_symlink() or not ROOT.is_dir():fail('Unexpected site root')
    for p in (PAGE,SITE):
        if p.is_symlink() or not p.is_file() or p.parent.is_symlink():fail('Unsafe main-only asset')
    if not (ROOT/'mpw-editorial/index.html').is_file():fail('Static directory identity missing')
    if not (ROOT/'.htaccess').is_file():fail('Main domain route missing')
def patch_page(original):
    text=original.decode('utf8')
    if PAGE_ID in text:fail('Page guide already exists')
    if text.count('</main>')!=1 or 'Details, terms &amp; next steps' not in text:fail('Page structure drift')
    if text.count('href="/accounts/register/"')>0:fail('Existing buyer registration guidance')
    newer=text.replace('</main>',SNIPPET+'</main>',1)
    if newer.replace(SNIPPET,'',1)!=text:fail('Page edit not bounded')
    return newer.encode('utf8')
def patch_sitemap(original):
    text=original.decode('utf8')
    marker='foreach ($paths as $path) {'
    if text.count(marker)!=1 or SITEMAP_ID in text:fail('Sitemap marker changed or already patched')
    if "'three-indexable-main-pages'" not in text and 'three-indexable-main-pages' not in text:fail('Main-only sitemap not recognized')
    if 'https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1' not in text:fail('Sitemap source identity not confirmed')
    for path in ROUTES:
        if path in text:fail('Duplicate sitemap URL in existing code')
    arr=','.join("'"+p+"'" for p in ROUTES)
    insertion=('// '+SITEMAP_ID+' -- 13 additional verified indexable main-domain pages\n'
               '$mpwRevenuePages20261020 = ['+arr+'];\n'
               'if (count($mpwRevenuePages20261020) !== 13 || count(array_unique($mpwRevenuePages20261020)) !== 13) fallbackSitemap();\n'
               '$paths = array_merge($paths, $mpwRevenuePages20261020);\n')
    newer=text.replace(marker,insertion+marker,1)
    if newer.replace(insertion,'',1)!=text:fail('Sitemap edit not bounded')
    return newer.encode('utf8')
def atomic(dest,content):
    mode=stat.S_IMODE(dest.stat().st_mode)
    fd,tmp=tempfile.mkstemp(prefix='.mpw-commerce-atomic-',dir=dest.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as out:out.write(content);out.flush();os.fsync(out.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def backup_dir(run):
    if not re.fullmatch('[0-9]{8,20}',run):fail('Bad run ID')
    return HOME/('.mpw-commercial-seo-'+run)
def lint_php(content):
    fd,tmp=tempfile.mkstemp(prefix='.mpw-commercial-php-lint-',suffix='.php',dir=SITE.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(content)
        check=subprocess.run(['php','-l',tmp],capture_output=True,text=True,timeout=15,check=False)
        if check.returncode!=0:fail('PHP lint failed: '+check.stderr[-150:])
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def publish(run):
    guard();records={};newbytes={}
    for key,path,patch in (('page',PAGE,patch_page),('sitemap',SITE,patch_sitemap)):
        old=path.read_bytes();new=patch(old)
        records[key]={'path':str(path),'before':digest(old),'after':digest(new)}
        newbytes[key]=(path,old,new)
    lint_php(newbytes['sitemap'][2])
    d=backup_dir(run)
    if d.exists() or d.is_symlink():fail('Backup already exists')
    d.mkdir(mode=0o700)
    for key,(_,old,_) in newbytes.items():
        p=d/(key+'.bak')
        with p.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    with (d/'manifest.json').open('x') as f:
        os.fchmod(f.fileno(),0o600)
        json.dump({'run':run,'files':records},f,sort_keys=True)
        f.flush();os.fsync(f.fileno())
    modified=[]
    try:
        for key,(path,old,new) in newbytes.items():
            if digest(path.read_bytes())!=records[key]['before']:fail('Concurrent modification of '+key)
            atomic(path,new)
            modified.append(key)
            if digest(path.read_bytes())!=records[key]['after']:fail('Failed write '+key)
    except BaseException:
        for key in reversed(modified):
            path,old,new=newbytes[key]
            if digest(path.read_bytes())==digest(new):atomic(path,old)
        raise
    print('MPW_COMMERCE_BUYER_AND_SITEMAP_INSTALLED='+json.dumps({'run':run,'main_site_only':True,'new_sitemap_entries':len(ROUTES),'payment_code_touched':False,'shared_django_touched':False,'before_after':records}))
def rollback(run):
    guard();d=backup_dir(run)
    if d.is_symlink() or not d.is_dir():fail('Missing backup')
    meta=json.loads((d/'manifest.json').read_text())
    if meta.get('run')!=run:fail('Wrong backup owner')
    items=[]
    for key,p in (('page',PAGE),('sitemap',SITE)):
        entry=meta['files'][key]
        b=d/(key+'.bak')
        if b.is_symlink() or not b.is_file() or digest(b.read_bytes())!=entry['before']:fail('Backup checksum mismatch')
        if str(p)!=entry['path'] or digest(p.read_bytes())!=entry['after']:fail('Concurrent post-release edit; rollback refused')
        items.append((p,b.read_bytes()))
    for p,old in items:atomic(p,old)
    for p,old in items:
        if digest(p.read_bytes())!=digest(old):fail('Rollback verification failure')
    print('MPW_COMMERCE_BUYER_AND_SITEMAP_ROLLBACK=VERIFIED')
def selftest():
    src=b'<!doctype html><html><body><main><h1>12 offers</h1>Details, terms &amp; next steps</main></body></html>'
    target=patch_page(src)
    assert target.replace(SNIPPET.encode(),'')==src and target.count(PAGE_ID.encode())==1
    sample=b"<?php\n$paths = ['/old/'];\nheader('X-MPW-Sitemap-Augmentation: three-indexable-main-pages');\n$foo='https://mojplaywin.com/sitemap.xml?__mpw_sitemap_passthru=1';\nforeach ($paths as $path) { echo $path; }\n"
    newer=patch_sitemap(sample)
    assert newer.count(SITEMAP_ID.encode())==1
    assert newer.count(b"/mpw-editorial/revenue/")==13
    print('MPW_COMMERCIAL_SEO_ATOMIC_SELFTEST=PASS')
if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
    elif len(sys.argv)==3 and sys.argv[1] in ('publish','rollback'):
        (publish if sys.argv[1]=='publish' else rollback)(sys.argv[2])
    else:raise SystemExit('Usage: selftest|publish RUN_ID|rollback RUN_ID')
