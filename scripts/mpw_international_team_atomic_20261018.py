#!/usr/bin/env python3
"""Add exactly one illustrative international-team section to the MojPlayWin main About page.

Atomic, reversible; no Django, Passenger, htaccess, other pages, child sites, or DB writes.
"""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
IMG=PAGE.parent/'mpw-international-team-20261018.webp'
HTACCESS=ROOT/'.htaccess'
EXPECTED_PAGE_SHA='b42821787eb7a5e32b4f6d17f8527b14547182c757f637d4f5a0c153d119b849'
MARKER='MPW_INTERNATIONAL_TEAM_ADDON_20261018'
SECTION='mpw-international-team-20261018'
EXPECTED_IMAGE_SHA='f947155b8cf9b4f86e19bff805fbc821a46319d6b435de5f935babc40a9da234'
EXPECTED_IMAGE_SIZE=300530
EXPECTED_NAMES=('Jessica','Claire','Emily','Sofia','Alessandra','Natalie','Larissa','Mika','Carlos','Liam')
EXISTING_MARKERS=('MPW_ABOUT_RESEARCH_80_20_V1','COMPLEMENTARY SPECIALISM 30',
                  'Original by Default','Mojtaba Roozegar','MPW_TEAM_ADDON_V1',
                  'mpw-meet-team-20261018','mpw-team-gallery-hq-20261018.webp',
                  'MPW_SENIOR_ADVISORY_ADDON_20261018','mpw-senior-advisory-20261018',
                  'mpw-senior-advisory-20261018.webp')

def sha(d):return hashlib.sha256(d).hexdigest()
def fail(m):raise RuntimeError(m)
def paths(runid):
    if not re.fullmatch(r'[0-9]{9,20}',runid):fail('Invalid release run identifier')
    home=ROOT.parent
    return (home/f'.mpw-intl-team-section-{runid}.html',
            home/f'.mpw-intl-team-image-{runid}.webp',
            home/f'.mpw-intl-team-backup-{runid}.html',
            home/f'.mpw-intl-team-manifest-{runid}.json')

def atomic(path,raw,mode):
    if path.is_symlink():fail('Refusing to write to symlink')
    fd,tmp=tempfile.mkstemp(prefix='.mpw-intl-team-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def check_existing_page():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail('Unexpected document root')
    if not PAGE.is_file() or PAGE.is_symlink() or not HTACCESS.is_file() or HTACCESS.is_symlink():fail('Unsafe About route or page')
    if any(x.is_symlink() for x in (PAGE.parent,PAGE.parent.parent,PAGE.parent.parent.parent)):
        fail('Unexpected symlink parent')
    rules=HTACCESS.read_text('utf-8',errors='replace')
    cond='RewriteCond %{REQUEST_URI} ^/about/$'
    rule='RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]'
    legacy='RewriteRule ^about/$ /design-preview-20261017/complete-about-20261018.html [END,QSD]'
    if not all(x in rules for x in ('MPW_ILLUSTRATED_TEN_PER_PAGE_20261018',cond,rule,legacy)):
        fail('Page routing no longer matches known isolated About deployment')
    if not rules.index(cond)<rules.index(rule)<rules.index(legacy):
        fail('About route rewrite precedence changed')
    if IMG.exists() or IMG.is_symlink():fail('Intended image path is occupied')
    original=PAGE.read_bytes()
    # The live About page may have gained other approved content since the last release.
    # Never overwrite it from an old snapshot: validate the current page in situ,
    # record its exact SHA, append precisely once, and recheck SHA before writing.
    if not 50000<=len(original)<=1500000:fail('Unexpected About page size')
    doc=original.decode('utf-8')
    if MARKER in doc or SECTION in doc:fail('New section already exists')
    if any(x not in doc for x in EXISTING_MARKERS):fail('Existing About section missing')
    if len(re.findall(r'<main\b',doc,re.I))!=1 or len(re.findall(r'</main\s*>',doc,re.I))!=1:fail('Unexpected main markup')
    if len(re.findall(r'<h1\b',doc,re.I))!=1:fail('Unexpected H1')
    if doc.count('class="mpw-team-card"')!=10 or doc.count('class="mpw-advisory-card"')!=10:
        fail('Existing employee or advisory profiles changed')
    return original

def validate_snippet(raw):
    if not 7000<=len(raw)<=16000:fail('Invalid international team section length')
    text=raw.decode('utf-8')
    if text.count(f'<section id="{SECTION}"')!=1:fail('Section missing or repeated')
    if text.count('class="mpw-intl-card"')!=10:fail('Expected exactly ten profiles')
    if text.count('mpw-international-team-20261018.webp')!=2:fail('Full-size image link missing')
    if 'not independently verified' not in text or 'digitally generated' not in text:
        fail('Clear illustration disclaimer required')
    for n in EXPECTED_NAMES:
        if f'<h3>{n}</h3>' not in text:fail('Missing profile '+n)
    if re.search(r'<script\b|<iframe\b|\{%|\{\{',text,re.I):fail('Executable templates forbidden')
    return text

def compose(old,snippet):
    if MARKER in old or SECTION in old:fail('Duplicate section forbidden')
    close=list(re.finditer(r'</main\s*>',old,re.I))
    if len(close)!=1:fail('Expected unique main closure')
    insertion='\n<!-- '+MARKER+' -->\n'+snippet+'\n'
    result=old[:close[0].start()]+insertion+old[close[0].start():]
    if result.replace(insertion,'',1)!=old:fail('Non-reversible append')
    if result.count('class="mpw-team-card"')!=10 or result.count('class="mpw-advisory-card"')!=10:
        fail('Unexpected mutation in existing cards')
    if len(re.findall(r'<h1\b',result,re.I))!=1:fail('H1 changed')
    if len(result.encode())>1550000:fail('Excessive page size')
    return result

def install(runid,section_sha,image_sha):
    stage_html,stage_img,backup,manifest=paths(runid)
    if not re.fullmatch(r'[0-9a-f]{64}',section_sha) or image_sha!=EXPECTED_IMAGE_SHA:
        fail('Invalid source sha')
    if not stage_html.is_file() or stage_html.is_symlink() or not stage_img.is_file() or stage_img.is_symlink():
        fail('Missing private staged sources')
    raw=stage_html.read_bytes()
    binary=stage_img.read_bytes()
    if sha(raw)!=section_sha:fail('HTML source does not match approved staged source')
    if sha(binary)!=EXPECTED_IMAGE_SHA or len(binary)!=EXPECTED_IMAGE_SIZE or binary[:4]!=b'RIFF' or binary[8:12]!=b'WEBP':
        fail('WebP source hash or format differs')
    section=validate_snippet(raw)
    before=check_existing_page()
    after=compose(before.decode('utf-8'),section).encode('utf-8')
    if backup.exists() or backup.is_symlink() or manifest.exists() or manifest.is_symlink():fail('Backup occupied')
    with backup.open('xb') as fh:
        os.chmod(backup,0o600);fh.write(before);fh.flush();os.fsync(fh.fileno())
    rec={'runid':runid,'before':sha(before),'after':sha(after),'image':sha(binary),'section':section_sha}
    with manifest.open('x',encoding='utf-8') as fh:
        os.chmod(manifest,0o600);json.dump(rec,fh);fh.flush();os.fsync(fh.fileno())
    if sha(PAGE.read_bytes())!=rec['before']:fail('Concurrent About update; fail closed')
    try:
        atomic(IMG,binary,0o644)
        if sha(IMG.read_bytes())!=rec['image']:fail('Image write verification failed')
        atomic(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
        if sha(PAGE.read_bytes())!=rec['after']:fail('Page write verification failed')
    except BaseException:
        if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==rec['after']:
            atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
        if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==rec['image']:
            IMG.unlink()
        raise
    stage_html.unlink();stage_img.unlink()
    print(json.dumps({'result':'MPW_INTERNATIONAL_TEAM_LIVE_PUBLISHED','profiles':10,
                      'html_sha_before':rec['before'],'html_sha_after':rec['after'],
                      'image_sha256':rec['image'],'image_bytes':len(binary),
                      'protected_pages_modified':False,'passenger_restarted':False,'rollback_saved':True}))

def rollback(runid):
    _,_,backup,manifest=paths(runid)
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():fail('Missing rollback evidence')
    rec=json.loads(manifest.read_text('utf-8'));old=backup.read_bytes()
    if sha(old)!=rec['before']:fail('Damaged rollback backup')
    if not PAGE.is_file() or PAGE.is_symlink():fail('Page no longer safe')
    current=sha(PAGE.read_bytes())
    if current==rec['after']:atomic(PAGE,old,stat.S_IMODE(PAGE.stat().st_mode))
    elif current!=rec['before']:fail('Concurrent edit; refuse destructive rollback')
    if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==rec['image']:IMG.unlink()
    elif IMG.exists() or IMG.is_symlink():fail('Image has changed; cannot delete')
    print(json.dumps({'result':'MPW_INTERNATIONAL_TEAM_ROLLED_BACK','current_page_sha':sha(PAGE.read_bytes())}))

def status(runid):
    _,_,backup,manifest=paths(runid)
    rec=json.loads(manifest.read_text('utf-8')) if manifest.is_file() else {}
    page_sha=sha(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else ''
    image_sha=sha(IMG.read_bytes()) if IMG.is_file() and not IMG.is_symlink() else ''
    print(json.dumps({'result':'MPW_INTERNATIONAL_TEAM_STATUS','installed':bool(rec) and rec.get('after')==page_sha and rec.get('image')==image_sha,
                      'page_sha256':page_sha,'image_sha256':image_sha,'rollback_exists':backup.is_file()}))

if __name__=='__main__':
    if len(sys.argv)<3:fail('usage: install|rollback|status RUN_ID [HTML_SHA IMAGE_SHA]')
    mode,id=sys.argv[1:3]
    if mode=='install' and len(sys.argv)==5:install(id,sys.argv[3],sys.argv[4])
    elif mode=='rollback' and len(sys.argv)==3:rollback(id)
    elif mode=='status' and len(sys.argv)==3:status(id)
    else:fail('Invalid mode')