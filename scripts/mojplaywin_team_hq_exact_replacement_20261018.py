#!/usr/bin/env python3
"""Replace *only* the known inline low-resolution MojPlayWin /about/ team image.

Strict SHA and route guards, independent full-resolution image asset, snapshot,
atomic page edit, and image-only rollback. No shared Django/Passenger or child edits.
"""
from pathlib import Path
import base64, hashlib, json, os, re, stat, sys, tempfile

ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html'
IMG=PAGE.parent/'mpw-team-gallery-hq-20261018.webp'
PUBLIC_IMAGE='/design-preview-20261017/mpw-ten-editorials-20261018/pages/mpw-team-gallery-hq-20261018.webp'
HTACCESS=ROOT/'.htaccess'
EXPECTED_PAGE_SHA='bc831aec453e67051093e4adde4dce4eb0a4dbbc875ed6f94db207adcf1e0ac3'
EXPECTED_INLINE_SHA='595d8fd7e314db2de2fa2a59570427505e7c623999b4f2d7aadae8018f949034'
EXPECTED_IMAGE_SHA='55eac88d17b4866a9f4db97e1ec3b2f69a50527f372619b3cebd83337a7f6a1d'
EXPECTED_DIMENSIONS=(1672,941)
MARKS=('MPW_ABOUT_RESEARCH_80_20_V1','COMPLEMENTARY SPECIALISM 30',
       'Original by Default','mpw-meet-team-20261018','MPW_TEAM_ADDON_V1',
       'The role focuses on evaluating opportunities')
NAMES=('Sophia','Isabella','Olivia','Camila','Valentina','Emma','Charlotte','Amelia','Luca','Noah')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def fail(msg):raise RuntimeError(msg)
def runid_check(v):
    if not re.fullmatch(r'[0-9]{9,20}',v): fail('Unsafe run ID')
    return v

def paths(runid):
    runid_check(runid)
    base=ROOT.parent
    return (base/f'.mpw-team-image-stage-{runid}.webp',
            base/f'.mpw-team-image-backup-{runid}.html',
            base/f'.mpw-team-image-manifest-{runid}.json')

def atomic_write(path,data,mode):
    if path.is_symlink():fail('Symlink target forbidden')
    fd,tmp=tempfile.mkstemp(prefix='.mpw-team-hi-',dir=str(path.parent))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as fh:
            fh.write(data);fh.flush();os.fsync(fh.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def ensure_page_route():
    if ROOT.is_symlink() or not ROOT.is_dir() or not PAGE.is_file() or PAGE.is_symlink():
        fail('Expected isolated About HTML not found')
    if any(path.is_symlink() for path in (PAGE.parent,PAGE.parent.parent,PAGE.parent.parent.parent)):
        fail('Unsafe About directory symlink')
    if not HTACCESS.is_file() or HTACCESS.is_symlink():fail('Unsafe root routing')
    rules=HTACCESS.read_text('utf-8',errors='replace')
    check=('MPW_ILLUSTRATED_TEN_PER_PAGE_20261018',
           'RewriteCond %{REQUEST_URI} ^/about/$',
           'RewriteRule ^.*$ /design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html [END,QSD]')
    if not all(x in rules for x in check):fail('Priority route no longer owns isolated About file')
    if IMG.exists() or IMG.is_symlink():fail('Proposed unique image asset path is already occupied')

def patch(original):
    if sha(original)!=EXPECTED_PAGE_SHA:fail('About page differs from last verified production version')
    data=original.decode('utf-8')
    if any(s not in data for s in MARKS):fail('Existing About dossier/team markers missing')
    if len(re.findall(r'class="mpw-team-card"',data))!=10:fail('Team member count changed')
    if any(f'<h3>{n}</h3>' not in data for n in NAMES):fail('Staff name missing')
    if len(re.findall(r'<h1\b',data,re.I))!=1:fail('Invalid About H1 count')
    anchor='<section id="mpw-meet-team-20261018"'
    if data.count(anchor)!=1:fail('Non-unique team section')
    section_start=data.index(anchor)
    figure_start=data.find('<figure>',section_start)
    figure_end=data.find('</figure>',figure_start)
    if not (section_start<figure_start<figure_end):fail('Missing original team gallery figure')
    figure=data[figure_start:figure_end]
    m=re.search(r'<img\s+[^>]*>',figure,re.I)
    if not m:fail('Gallery has no image tag')
    old_tag=m.group(0)
    b=re.search(r'src="data:image/avif;base64,([a-zA-Z0-9+/=]+)"',old_tag)
    if not b:fail('Expected old inline AVIF no longer exists')
    if len(re.findall(r'data:image/avif;base64,',figure))!=1:fail('Not a unique inline image')
    raw=base64.b64decode(b.group(1),validate=True)
    if sha(raw)!=EXPECTED_INLINE_SHA:fail('Old image has changed unexpectedly')
    if 'width="720" height="480"' not in old_tag:fail('Old image dimensions changed')
    new_tag=old_tag.replace(b.group(0),f'src="{PUBLIC_IMAGE}"',1)
    new_tag=new_tag.replace('width="720" height="480"','width="1672" height="941"',1)
    updated=data[:figure_start+m.start()]+new_tag+data[figure_start+m.end():]
    if updated.replace(new_tag,old_tag,1)!=data:fail('Patch not exactly reversible')
    if updated.count(PUBLIC_IMAGE)!=1:fail('Unexpected public asset references')
    if any(x not in updated for x in MARKS):fail('Existing content lost')
    if updated.count('class="mpw-team-card"')!=10:fail('Modified cards')
    return updated.encode('utf-8')

def install(runid):
    stage,backup,manifest=paths(runid)
    ensure_page_route()
    if not stage.is_file() or stage.is_symlink():fail('Private staged asset missing')
    image=stage.read_bytes()
    if sha(image)!=EXPECTED_IMAGE_SHA or not image.startswith(b'RIFF') or image[8:12]!=b'WEBP':
        fail('Staged WebP SHA/type mismatch')
    before=PAGE.read_bytes()
    after=patch(before)
    if backup.exists() or backup.is_symlink() or manifest.exists() or manifest.is_symlink():
        fail('Run backup already present')
    with backup.open('xb') as f:
        os.chmod(backup,0o600);f.write(before);f.flush();os.fsync(f.fileno())
    record={'runid':runid,'before':sha(before),'after':sha(after),
            'image_sha':sha(image),'asset_path':str(IMG)}
    with manifest.open('x',encoding='utf-8') as f:
        os.chmod(manifest,0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    if sha(PAGE.read_bytes())!=record['before']:fail('Concurrent About edit')
    try:
        atomic_write(IMG,image,0o644)
        if sha(IMG.read_bytes())!=record['image_sha']:fail('Installed image hash mismatch')
        atomic_write(PAGE,after,stat.S_IMODE(PAGE.stat().st_mode))
        if sha(PAGE.read_bytes())!=record['after']:fail('Installed HTML hash mismatch')
    except BaseException:
        if PAGE.is_file() and sha(PAGE.read_bytes())==record['after']:
            atomic_write(PAGE,before,stat.S_IMODE(PAGE.stat().st_mode))
        if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==record['image_sha']:
            IMG.unlink()
        raise
    stage.unlink()
    print(json.dumps({'status':'HIGH_QUALITY_TEAM_IMAGE_REPLACED','html_before_sha':record['before'],
                      'html_after_sha':record['after'],'asset_sha':record['image_sha'],
                      'image_bytes':len(image),'dimensions':'1672x941','other_pages_changed':False,
                      'passenger_restarted':False,'rollback_prepared':True}))

def rollback(runid):
    stage,backup,manifest=paths(runid)
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        fail('No valid backup for this run')
    record=json.loads(manifest.read_text('utf-8'))
    old=backup.read_bytes()
    if sha(old)!=record['before']:fail('Backup data corrupt')
    if not PAGE.is_file() or PAGE.is_symlink():fail('About file missing')
    current=sha(PAGE.read_bytes())
    if current==record['after']:
        atomic_write(PAGE,old,stat.S_IMODE(PAGE.stat().st_mode))
    elif current!=record['before']:
        fail('Concurrent About change; refuse rollback overwrite')
    if IMG.is_file() and not IMG.is_symlink() and sha(IMG.read_bytes())==record['image_sha']:
        IMG.unlink()
    elif IMG.exists() or IMG.is_symlink():fail('Image has changed; refuse deletion')
    print(json.dumps({'status':'RESTORED_LOW_QUALITY_TEAM_IMAGE','sha':sha(PAGE.read_bytes())}))

def status(runid):
    _,backup,manifest=paths(runid)
    rec=json.loads(manifest.read_text('utf-8')) if manifest.is_file() else {}
    page_hash=sha(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else None
    image_hash=sha(IMG.read_bytes()) if IMG.is_file() and not IMG.is_symlink() else None
    print(json.dumps({'status':'READ_ONLY_HIGH_QUALITY_TEAM_IMAGE','installed':bool(rec) and page_hash==rec.get('after') and image_hash==rec.get('image_sha'),
                      'html_sha':page_hash,'image_sha':image_hash,'backup_exists':backup.is_file()}))

if __name__=='__main__':
    if len(sys.argv)!=3:fail('Use install|rollback|status RUN_ID')
    mode,runid=sys.argv[1:]
    if mode=='install':install(runid)
    elif mode=='rollback':rollback(runid)
    elif mode=='status':status(runid)
    else:fail('Unknown mode')