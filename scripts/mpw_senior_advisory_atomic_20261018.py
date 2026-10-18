#!/usr/bin/env python3
"""Fail-closed additive /about/ advisory release; no shared or child-site writes."""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
IMG=PAGE.parent/'mpw-senior-advisory-20261018.webp'
HTACCESS=ROOT/'.htaccess'
SHA_IMAGE='1d8b4f232e7938064142b51d07b40345a079a205e9381c05cbcc366b073be70e'
MARKER='MPW_SENIOR_ADVISORY_ADDON_20261018'
SECTION='mpw-senior-advisory-20261018'
TEAM_MARKER='mpw-meet-team-20261018'
PRESENT_MARKERS=("MPW_ABOUT_RESEARCH_80_20_V1", "COMPLEMENTARY SPECIALISM 30",
                 "Original by Default", "Mojtaba Roozegar", TEAM_MARKER,
                 "MPW_TEAM_ADDON_V1", "mpw-team-gallery-hq-20261018.webp")
STAFF=('Sophia','Isabella','Olivia','Camila','Valentina','Emma','Charlotte','Amelia','Luca','Noah')
ADVISORS=('Dr. Margaret Wilson','Prof. Thomas Bennett','Dr. Susan Clarke',
          'Prof. James Anderson','Dr. Helen Morris','Prof. Robert Hughes',
          'Dr. Patricia Moore','Prof. William Carter','Dr. Linda Foster',
          'Prof. Richard Taylor')

def sha(data):return hashlib.sha256(data).hexdigest()
def fail(reason):raise RuntimeError(reason)
def getpaths(runid):
    if not re.fullmatch(r'[0-9]{9,20}',runid):fail('Invalid release identifier')
    h=ROOT.parent
    return (h/f'.mpw-advisory-section-{runid}.html',
            h/f'.mpw-advisory-image-{runid}.webp',
            h/f'.mpw-advisory-backup-{runid}.html',
            h/f'.mpw-advisory-manifest-{runid}.json')

def atomic(path,data,mode):
    if path.is_symlink():fail('Cannot write symlink')
    fd,tmp=tempfile.mkstemp(prefix='.mpw-advisory-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def guard():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:fail('Unexpected docroot')
    if not PAGE.is_file() or PAGE.is_symlink() or not HTACCESS.is_file() or HTACCESS.is_symlink():fail('About page/routing unsafe')
    if any(p.is_symlink() for p in (PAGE.parent,PAGE.parent.parent,PAGE.parent.parent.parent)):
        fail('Refuse symlink in parent path')
    rules=HTACCESS.read_text('utf-8',errors='replace')
    cond='RewriteCond %{REQUEST_URI} ^/about/$'
    rule='RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]'
    legacy='RewriteRule ^about/$ /design-preview-20261017/complete-about-20261018.html [END,QSD]'
    if not all(x in rules for x in ('MPW_ILLUSTRATED_TEN_PER_PAGE_20261018',cond,rule,legacy)) or rules.index(rule)>rules.index(legacy):
        fail('Live /about/ routing precedence differs from verified release')
    if IMG.exists() or IMG.is_symlink():fail('Advisory image destination is occupied')
    original=PAGE.read_bytes()
    if not 50_000<=len(original)<1_500_000:fail('About page unexpected size')
    raw=original.decode('utf-8')
    if MARKER in raw or SECTION in raw:fail('Advisory section already exists')
    if any(m not in raw for m in PRESENT_MARKERS):fail('Existing original/team markers missing')
    if len(re.findall(r'<main\b',raw,re.I))!=1 or len(re.findall(r'</main\s*>',raw,re.I))!=1:fail('Unexpected main landmarks')
    if raw.count('class="mpw-team-card"')!=10:fail('Employee profiles changed')
    if any(f'<h3>{name}</h3>' not in raw for name in STAFF):fail('Existing employee not found')
    if len(re.findall(r'<h1\b',raw,re.I))!=1:fail('Original H1 unexpected')
    return original

def validate_snippet(raw):
    if not 8_500 <= len(raw) <= 16_000:fail('Advisory section size invalid')
    s=raw.decode('utf-8')
    if s.count(f'<section id="{SECTION}"')!=1:fail('Unique advisory section missing')
    if s.count('class="mpw-advisory-card"')!=10:fail('Expected ten advisory cards')
    if s.count('mpw-senior-advisory-20261018.webp')!=2:fail('Image and enlargement link missing')
    if 'not independently verified' not in s:fail('Illustrative image disclosure missing')
    if any(n not in s for n in ADVISORS):fail('Advisory card is missing')
    if re.search(r'<script\b|<iframe\b|\{%|\{\{',s,re.I):fail('Executable code prohibited')
    return s

def compose(old,snippet):
    if MARKER in old or SECTION in old:fail('Duplicate publication forbidden')
    closing=list(re.finditer(r'</main\s*>',old,re.I))
    if len(closing)!=1:fail('Missing unique main close')
    addon='\n<!-- '+MARKER+' -->\n'+snippet+'\n'
    pos=closing[0].start()
    new=old[:pos]+addon+old[pos:]
    if new.replace(addon,'',1)!=old:fail('Not perfectly reversible')
    if len(re.findall(r'<h1\b',new,re.I))!=1 or new.count('class="mpw-team-card"')!=10:fail('Existing semantics changed')
    if len(new.encode('utf-8'))>1_530_000:fail('Page too large')
    return new

def install(runid,expected_html,expected_image):
    stage_html,stage_img,backup,manifest=getpaths(runid)
    if not re.fullmatch('[a-f0-9]{64}',expected_html) or expected_image!=SHA_IMAGE:fail('Invalid source hashes')
    if not stage_html.is_file() or stage_html.is_symlink() or not stage_img.is_file() or stage_img.is_symlink():fail('Missing staged files')
    html_raw=stage_html.read_bytes();image=stage_img.read_bytes()
    if sha(html_raw)!=expected_html:fail('Staged HTML digest mismatch')
    if sha(image)!=SHA_IMAGE or not image.startswith(b'RIFF') or image[8:12]!=b'WEBP' or not 100000<len(image)<1000000:
        fail('Staged photo does not match approved WebP')
    snippet=validate_snippet(html_raw)
    before=guard();after=compose(before.decode('utf-8'),snippet).encode('utf-8')
    if backup.exists() or backup.is_symlink() or manifest.exists() or manifest.is_symlink():fail('Existing run backup')
    with backup.open('xb') as f:
        os.chmod(backup,0o600);f.write(before);f.flush();os.fsync(f.fileno())
    record={'id':runid,'before':sha(before),'after':sha(after),'image':sha(image),'snippet':expected_html,'path':str(PAGE)}
    with manifest.open('x',encoding='utf-8') as f:
        os.chmod(manifest,0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    if sha(PAGE.read_bytes())!=record['before']:fail('Concurrent About edit')
    try:
        atomic(IMG,image,0o644)
        if sha(IMG.read_bytes())!=SHA_IMAGE:fail('Public photo hash mismatch')
        atomic(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
        if sha(PAGE.read_bytes())!=record['after']:fail('About page commit mismatch')
    except BaseException:
        if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==record['after']:
            atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
        if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==SHA_IMAGE:
            IMG.unlink()
        raise
    stage_html.unlink();stage_img.unlink()
    print(json.dumps({'result':'MPW_ADVISORY_ABOUT_PUBLISHED','page_sha_before':record['before'],
                      'page_sha_after':record['after'],'profiles':10,'image_sha':SHA_IMAGE,
                      'passenger_restart':False,'other_pages_modified':False,'rollback_saved':True}))

def rollback(runid):
    _,_,backup,manifest=getpaths(runid)
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():fail('Backup missing')
    r=json.loads(manifest.read_text('utf-8'))
    before=backup.read_bytes()
    if sha(before)!=r['before']:fail('Backup corrupt')
    if not PAGE.is_file() or PAGE.is_symlink():fail('Page missing')
    current=sha(PAGE.read_bytes())
    if current==r['after']:
        atomic(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
    elif current!=r['before']:
        fail('Concurrent edit detected; refusing to overwrite')
    if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==r['image']:
        IMG.unlink()
    elif IMG.exists() or IMG.is_symlink():fail('Image changed; cannot delete')
    print(json.dumps({'result':'MPW_ADVISORY_ABOUT_ROLLED_BACK','current_sha':sha(PAGE.read_bytes())}))

def status(runid):
    _,_,backup,manifest=getpaths(runid)
    rec=json.loads(manifest.read_text('utf-8')) if manifest.is_file() else {}
    current=sha(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else ''
    ih=sha(IMG.read_bytes()) if IMG.is_file() and not IMG.is_symlink() else ''
    print(json.dumps({'result':'MPW_ADVISORY_ABOUT_STATUS','installed':bool(rec) and current==rec.get('after') and ih==rec.get('image'),
                      'rollback_exists':backup.is_file(),'current_page_sha':current,'image_sha':ih}))

if __name__=='__main__':
    if len(sys.argv)<3:fail('Usage: install|rollback|status RUNID [HTML_SHA IMAGE_SHA]')
    mode,id=sys.argv[1:3]
    if mode=='install' and len(sys.argv)==5:install(id,sys.argv[3],sys.argv[4])
    elif mode=='rollback' and len(sys.argv)==3:rollback(id)
    elif mode=='status' and len(sys.argv)==3:status(id)
    else:fail('Invalid arguments')