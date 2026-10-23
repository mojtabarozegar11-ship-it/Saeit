#!/usr/bin/env python3
"""Guarded exact-scope static publish to the MojPlayWin game-releases namespace."""
import hashlib,json,os,re,shutil,sys
from pathlib import Path

HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
PARENT=ROOT/'game-releases'
TARGET=PARENT/'20261023-next'
REQUIRED=['index.html','hashes.json','release.json','assets/theme.css','assets/arcade.js','assets/workshop.js']
GAMES=['hex-bloom','prism-relay','kitchen-rush','type-defender','codebreaker-vault']
TOOLS=['file-fingerprint','meeting-time-planner','subtitle-shifter','text-diff-lab','passphrase-forge']
HT=b'PassengerEnabled off\nDirectoryIndex index.html\n'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stage(run):return HOME/('.mpw-next-tenlab-stage-'+run)
def meta(run):return stage(run)/'deploy.json'
def record(run,data):
    m=meta(run);t=m.with_suffix('.new')
    t.write_text(json.dumps(data,sort_keys=True),encoding='utf8')
    os.replace(t,m)
def require_safe():
    for p in [HOME,ROOT,PARENT]:
        if not p.is_dir() or p.is_symlink():raise RuntimeError('unsafe cPanel folder '+str(p))
    if TARGET.exists() or TARGET.is_symlink():raise RuntimeError('release destination already exists; overwrite prohibited')
    if not (ROOT/'passenger_wsgi.py').is_file():raise RuntimeError('unexpected MojPlayWin host root')
def payload_files(run):
    p=stage(run)/'payload'
    if not p.is_dir() or p.is_symlink():raise RuntimeError('payload stage not a directory')
    hashes=json.loads((p/'hashes.json').read_text('utf8'))
    expected=(set(REQUIRED)-{'hashes.json'}) | {x+'/index.html' for x in GAMES+TOOLS}
    if not expected.issubset(set(hashes)):raise RuntimeError('required product not in manifest')
    actual={str(x.relative_to(p)) for x in p.rglob('*') if x.is_file()}
    if actual != set(hashes)|{'hashes.json'}:raise RuntimeError('unexpected or missing staged files')
    for rel,dig in hashes.items():
        dest=p/rel
        if any(part in ('..','.') for part in Path(rel).parts) or Path(rel).is_absolute() or dest.is_symlink() or not dest.is_file():
            raise RuntimeError('unsafe asset path: '+rel)
        if digest(dest)!=dig:raise RuntimeError('asset sha mismatch: '+rel)
    manifest=json.loads((p/'release.json').read_text('utf8'))
    if len(manifest['games'])!=5 or len(manifest['tools'])!=5 or manifest['language']!='en':raise RuntimeError('incorrect bundle counts')
    return p,hashes
def prepare(run,commit):
    require_safe()
    p,hashes=payload_files(run)
    if meta(run).exists():raise RuntimeError('release id already used')
    protected={}
    for rel in ['passenger_wsgi.py','.htaccess','game-releases/20261021/index.html','mpw-editorial/index.html']:
        f=ROOT/rel
        if f.is_symlink():raise RuntimeError('protected symlink')
        if f.is_file():protected[rel]=digest(f)
    if len(protected)<2:raise RuntimeError('too few original protected page baselines')
    record(run,{'phase':'prepared','commit':commit,'protected':protected,'hashes':hashes,'files':[]})
    print('MPW_TENLAB_PRIVATE_STAGE_VERIFIED=PASS')
def guard(m):
    for rel,h in m['protected'].items():
        f=ROOT/rel
        if not f.is_file() or f.is_symlink() or digest(f)!=h:raise RuntimeError('protected site changed: '+rel)
def publish(run,commit):
    m=json.loads(meta(run).read_text('utf8'))
    if m['phase']!='prepared' or m['commit']!=commit:raise RuntimeError('invalid publish phase / sha')
    require_safe();guard(m)
    p,hashes=payload_files(run)
    route=p/'.htaccess'
    if route.exists() or route.is_symlink():raise RuntimeError('unexpected route .htaccess')
    route.write_bytes(HT)
    m['hashes']['.htaccess']=digest(route)
    m['files']=sorted(m['hashes'])
    record(run,m)
    if TARGET.exists() or TARGET.is_symlink():raise RuntimeError('concurrent publish')
    os.rename(p,TARGET)
    m['phase']='published';record(run,m)
    print('MPW_SECOND_TEN_DISTINCT_APPS_INSTALLED=PASS',flush=True)
def verify(run,commit):
    m=json.loads(meta(run).read_text('utf8'))
    if m['phase']!='published' or m['commit']!=commit:raise RuntimeError('not installed')
    guard(m)
    actual={str(p.relative_to(TARGET)) for p in TARGET.rglob('*') if p.is_file()}
    if actual!=(set(m['hashes'])|{'hashes.json'}):raise RuntimeError('unexpected live asset')
    for rel,h in m['hashes'].items():
        p=TARGET/rel
        if not p.is_file() or p.is_symlink() or digest(p)!=h:raise RuntimeError('live asset mismatch: '+rel)
    print('MPW_SECOND_TEN_HASH_AND_ORIGINALS=PASS',flush=True)
def rollback(run,commit):
    if not meta(run).is_file():print('MPW_ROLLBACK_NOT_NEEDED');return
    m=json.loads(meta(run).read_text('utf8'))
    if m.get('commit')!=commit:raise RuntimeError('different release id')
    if not TARGET.exists():return
    if TARGET.is_symlink() or not TARGET.is_dir():raise RuntimeError('refuse unsafe rollback')
    actual={str(p.relative_to(TARGET)) for p in TARGET.rglob('*') if p.is_file()}
    if actual!=(set(m['hashes'])|{'hashes.json'}):raise RuntimeError('foreign files found; cannot safely rollback')
    for rel,h in m['hashes'].items():
        p=TARGET/rel
        if p.is_symlink() or not p.is_file() or digest(p)!=h:raise RuntimeError('foreign edit found; rollback refused '+rel)
    shutil.rmtree(TARGET)
    m['phase']='rolled_back';record(run,m)
    print('MPW_TENLAB_ONLY_CREATED_ROUTE_ROLLED_BACK=PASS',flush=True)
if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1] not in ('prepare','publish','verify','rollback') or not re.fullmatch(r'[0-9]{7,17}',sys.argv[2]) or not re.fullmatch(r'[0-9a-f]{40}',sys.argv[3]):raise SystemExit('deploy.py prepare|publish|verify|rollback RUN_ID SHA')
    globals()[sys.argv[1]](*sys.argv[2:])
