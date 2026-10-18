#!/usr/bin/env python3
"""Append the MojPlayWin team section to exactly one existing static /about/ page.

Production mutation is limited to one About HTML asset. An exact, reversible
snapshot is stored outside webroot. The shared Django runtime, Passenger,
.htaccess, databases, checkout and child sites are never modified.
"""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile

ROOT=Path('/home/zomorod2/mojplaywin.com')
PAGE=ROOT/'design-preview-20261017/complete-about-20261018.html'
HTACCESS=ROOT/'.htaccess'
SECTION_MARKER='mpw-meet-team-20261018'
EXISTING_MARKERS=('Original by Default','MPW_ABOUT_RESEARCH_80_20_V1',
                  'SPECIALISM 28','COMPLEMENTARY SPECIALISM 30','Mojtaba Roozegar')

def sha(data):return hashlib.sha256(data).hexdigest()
def die(reason):raise RuntimeError(reason)
def safeid(runid):
    if not re.fullmatch(r'[0-9]{9,20}',runid):die('Invalid workflow run ID')
    return runid

def paths(runid):
    runid=safeid(runid)
    return (ROOT.parent/f'.mpw-team-stage-{runid}.html',
            ROOT.parent/f'.mpw-team-backup-{runid}.html',
            ROOT.parent/f'.mpw-team-manifest-{runid}.json')

def safe_write(target,raw,mode):
    if target.is_symlink():die('Refuse symlink target')
    fd,temp=tempfile.mkstemp(prefix='.mpw-team-atomic-',dir=target.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def guard():
    if not ROOT.is_dir() or ROOT.is_symlink() or not PAGE.is_file() or PAGE.is_symlink():
        die('About production file does not match known isolated layout')
    if not HTACCESS.is_file() or HTACCESS.is_symlink():die('Routing file absent or unsafe')
    rules=HTACCESS.read_text('utf-8',errors='replace')
    if not all(x in rules for x in (
        'MPW_EXACT_ABOUT_80_20_20261018',
        'RewriteCond %{REQUEST_URI} ^/about/$',
        'RewriteRule ^about/$ /design-preview-20261017/complete-about-20261018.html')):
        die('Existing About route no longer points to exact isolated file')
    original=PAGE.read_bytes()
    if not 50_000<=len(original)<=1_500_000:die('About content size outside safety bounds')
    old=original.decode('utf-8')
    for mark in EXISTING_MARKERS:
        if mark not in old:die('Existing About marker missing: '+mark)
    if SECTION_MARKER in old:die('Team section already installed: refuse duplicate')
    if len(re.findall(r'<main\b',old,re.I))!=1 or len(re.findall(r'</main\s*>',old,re.I))!=1:
        die('Unexpected semantic main landmarks')
    return original,old

def compose(old,snippet):
    if not 22_000<=len(snippet.encode('utf-8'))<=45_000:die('Team snippet size invalid')
    if snippet.count('data:image/avif;base64,')!=1:die('Image is missing or duplicated')
    if snippet.count('class="mpw-team-card"')!=10:die('Exactly 10 team members required')
    if snippet.count('<section id="mpw-meet-team-20261018"')!=1:die('Invalid section marker')
    if re.search(r'<script\b|<iframe\b|\{%|\{\{',snippet,re.I):die('No executable or unrendered content allowed')
    for name in ('Sophia','Isabella','Olivia','Camila','Valentina','Emma','Charlotte','Amelia','Luca','Noah'):
        if f'<h3>{name}</h3>' not in snippet:die('Profile missing: '+name)
    closing=list(re.finditer(r'</main\s*>',old,re.I))
    if len(closing)!=1:die('No unique main closing tag')
    pos=closing[0].start()
    patched=old[:pos]+'\n<!-- MPW_TEAM_ADDON_V1 -->\n'+snippet+'\n'+old[pos:]
    if len(patched.encode('utf-8'))>1_550_000:die('Result too large')
    if len(re.findall(r'<h1\b',patched,re.I))!=len(re.findall(r'<h1\b',old,re.I)):die('H1 changed')
    for mark in EXISTING_MARKERS:
        if mark not in patched:die('Original editorial material damaged')
    # Removing only the newly added bytes must reconstruct the original exactly.
    if patched.replace('\n<!-- MPW_TEAM_ADDON_V1 -->\n'+snippet+'\n','',1)!=old:
        die('Patch is not byte-reversible')
    return patched.encode('utf-8')

def install(runid,digest):
    stage,backup,manifest=paths(runid)
    if not re.fullmatch(r'[a-f0-9]{64}',digest):die('Invalid expected hash')
    if not stage.is_file() or stage.is_symlink():die('Staged content unavailable')
    snippet_raw=stage.read_bytes()
    if sha(snippet_raw)!=digest:die('Staged payload digest changed')
    original,old=guard()
    if any(x.exists() or x.is_symlink() for x in (backup,manifest)):
        die('This run already has a backup or manifest')
    updated=compose(old,snippet_raw.decode('utf-8'))
    with open(backup,'xb') as f:
        os.chmod(backup,0o600)
        f.write(original);f.flush();os.fsync(f.fileno())
    record={'runid':runid,'before':sha(original),'after':sha(updated),
            'about_path':str(PAGE),'payload_sha':digest,'profile_count':10}
    with open(manifest,'x',encoding='utf-8') as f:
        os.chmod(manifest,0o600)
        json.dump(record,f);f.flush();os.fsync(f.fileno())
    mode=stat.S_IMODE(PAGE.stat().st_mode)
    # Prevent another worker from winning between the initial guard and write.
    if sha(PAGE.read_bytes())!=sha(original):die('Concurrent About edit; refusing overwrite')
    try:
        safe_write(PAGE,updated,mode)
        if sha(PAGE.read_bytes())!=sha(updated):die('Post-install hash mismatch')
    except BaseException:
        if PAGE.is_file() and not PAGE.is_symlink() and sha(PAGE.read_bytes())==sha(updated):
            safe_write(PAGE,original,mode)
        raise
    stage.unlink()
    print(json.dumps({'status':'PUBLISHED_TEAM_ONLY','page_sha_before':sha(original),
                      'page_sha_after':sha(updated),'profiles':10,'passenger_restart':False,
                      'other_files_changed':False,'rollback_path':str(backup)}))

def rollback(runid):
    _,backup,manifest=paths(runid)
    if not backup.is_file() or backup.is_symlink() or not manifest.is_file() or manifest.is_symlink():
        die('Recovery evidence missing')
    record=json.loads(manifest.read_text('utf-8'))
    old=backup.read_bytes()
    if sha(old)!=record['before']:die('Recovery backup corrupt')
    if not PAGE.is_file() or PAGE.is_symlink():die('Target changed type')
    current=PAGE.read_bytes()
    if sha(current)!=record['after']:die('Unexpected newer edit; refuse destructive rollback')
    safe_write(PAGE,old,stat.S_IMODE(PAGE.stat().st_mode))
    if sha(PAGE.read_bytes())!=record['before']:die('Rollback verification failed')
    print(json.dumps({'status':'ROLLED_BACK_TEAM_ONLY','restored_sha':record['before']}))

def status(runid):
    _,backup,manifest=paths(runid)
    record=json.loads(manifest.read_text('utf-8')) if manifest.is_file() else {}
    curr=sha(PAGE.read_bytes()) if PAGE.is_file() and not PAGE.is_symlink() else None
    print(json.dumps({'status':'TEAM_READONLY_STATUS','installed':curr==record.get('after'),
                      'backup_present':backup.is_file(),'current_sha':curr,
                      'expected_sha':record.get('after')}))

if __name__=='__main__':
    if len(sys.argv)<3:die('Use install|rollback|status RUN_ID [SOURCE_SHA]')
    action=sys.argv[1]
    if action=='install' and len(sys.argv)==4:install(sys.argv[2],sys.argv[3])
    elif action=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
    elif action=='status' and len(sys.argv)==3:status(sys.argv[2])
    else:die('Unknown mode or arguments')