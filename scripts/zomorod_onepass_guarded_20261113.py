#!/usr/bin/env python3
"""Safe, exactly-scoped Zomorod one-pass homepage, three rotators, official alpha logo & stable static Arabic HTML release.

Existing website internals, domain settings, .htaccess, orders and databases are read-only.
Requires explicit old Git revision to match live before any writes.
"""
from __future__ import annotations
import fcntl, hashlib, json, os, pwd, re, stat, sys, tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT=Path('/home/zomorod2/public_html')
STAGE=Path(__file__).resolve().parent
BACKUP_ROOT=Path('/home/zomorod2/.backups/zomorod-vision-onepass-20261113')
LOCK=BACKUP_ROOT.parent/'.zomorod-homepage-deploy.lock'
REPLACE=("index.html","assets/zm-reference-v3.css","assets/zm-reference-v3.js")
CREATE=("assets/zm-logo-transparent-v1.webp","assets/zm-ar-v1.html")
PROTECTED=(
 '.htaccess','sitemap.xml','agriculture/index.html','research/index.html',
 'industry/index.html','services/index.html','company/index.html','contact/index.html',
 'store/index.php','games/index.html','apps/index.html','auctions/index.html',
 'static/site/zomorod-v7/company-logo.webp',
 'site-heritage/home-before-nexus-20261112/index.html',
)
RIGHTS='آبان ۱۳۹۸ | کلیه حقوق مادی و معنوی محفوظ است.'.encode('utf-8')

def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def safe(path:Path)->bytes:
 if path.is_symlink() or not path.is_file():raise RuntimeError('Missing or symlinked: '+str(path))
 return path.read_bytes()
def root_guard():
 if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2':raise RuntimeError('Wrong hosting identity')
 for p in (ROOT,ROOT/'assets',STAGE,BACKUP_ROOT.parent):
  if not p.is_dir() or p.is_symlink():raise RuntimeError('Unsafe base directory: '+str(p))
 for p in (BACKUP_ROOT,LOCK):
  if p.is_symlink():raise RuntimeError('Unsafe symbolic link: '+str(p))
def key(run):
 if not re.fullmatch(r'vision-[0-9]{7,22}',run):raise RuntimeError('Bad release ID')
 return BACKUP_ROOT/run

def fingerprint_protected():
 result={}
 for rel in PROTECTED:
  p=ROOT/rel
  if p.exists():result[rel]=digest(safe(p))
 if len(result)<10:raise RuntimeError('Too few protected internal files')
 return result

def candidates():
 source={rel:safe(STAGE/'new'/rel) for rel in REPLACE+CREATE}
 previous={rel:safe(STAGE/'old'/rel) for rel in REPLACE}
 if not all(source[x]!=previous[x] for x in REPLACE):raise RuntimeError('Unexpected unchanged replacement')
 if source['index.html'].count(RIGHTS)!=1:raise RuntimeError('Footer rights lost')
 if not all(s in source['index.html'] for s in (
   b'zm-reference-v3.css?v=20261113-all1',b'zm-reference-v3.js?v=20261113-all1',
   b'data-auto-strip="services-strip"',b'data-auto-strip="products-strip"',
   b'data-auto-strip="projects-strip"',b'action="/search/"',b'href="/en/"',b'href="/assets/zm-ar-v1.html"',
   b'assets/zm-logo-transparent-v1.webp',b'lang="fa"')):
  raise RuntimeError('Homepage feature contract incomplete')
 if source['index.html'].count(b'data-auto-strip=')!=3:raise RuntimeError('Wrong rotating row count')
 if source['index.html'].count(b'data-rotator-toggle=')!=3:raise RuntimeError('Missing motion control')
 if not all(x in source['assets/zm-reference-v3.js'] for x in (b'setInterval',b'prefers-reduced-motion',b'carousel-copy',b'paused')):
  raise RuntimeError('Real row controller absent')
 img=source['assets/zm-logo-transparent-v1.webp']
 if len(img)<25000 or img[:4]!=b'RIFF' or img[8:12]!=b'WEBP':raise RuntimeError('Transparent official logo file missing')
 if b'<html lang="ar" dir="rtl">' not in source['assets/zm-ar-v1.html'] or b'/contact/' not in source['assets/zm-ar-v1.html']:
  raise RuntimeError('Arabic landing does not contain genuine Arabic site content')
 for forbidden in ('Vancouver','ونکوور','ISO 9001','ISO 14001','+650','+600'):
  if forbidden.encode() in source['index.html']:raise RuntimeError('Unverified statement: '+forbidden)
 return previous,source

def atomic(path:Path,data:bytes,mode=0o644):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-onepass-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode);os.replace(temp,path)
 finally:
  if temp is not None and temp.exists():temp.unlink()

@contextmanager
def lock():
 with open(LOCK,'a+b') as f:
  fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def preflight():
 root_guard();previous,new=candidates()
 for rel in REPLACE:
  if digest(safe(ROOT/rel))!=digest(previous[rel]):raise RuntimeError('Live revision differs from pinned baseline: '+rel)
 for rel in CREATE:
  p=ROOT/rel
  if p.exists() or p.is_symlink():raise RuntimeError('Create-only file already present: '+rel)
 if BACKUP_ROOT.exists() and not BACKUP_ROOT.is_dir():raise RuntimeError('Unsafe backup root')
 return {'replace':{rel:{'before':digest(previous[rel]),'after':digest(new[rel]),'mode':stat.S_IMODE((ROOT/rel).stat().st_mode)} for rel in REPLACE},
         'create':{rel:digest(new[rel]) for rel in CREATE},'protected':fingerprint_protected()}

def load(run):
 dir=key(run)
 manifest=json.loads(safe(dir/'manifest.json').decode())
 old={rel:safe(dir/'old'/rel) for rel in REPLACE}
 for rel in REPLACE:
  if digest(old[rel])!=manifest['replace'][rel]['before']:raise RuntimeError('Backup corruption '+rel)
 return dir,manifest,old

def ensure_unchanged(manifest):
 if fingerprint_protected()!=manifest['protected']:raise RuntimeError('Internal source checksum changed')

def verify(run):
 root_guard();dir,manifest,old=load(run)
 ensure_unchanged(manifest)
 for rel in REPLACE:
  if digest(safe(ROOT/rel))!=manifest['replace'][rel]['after']:raise RuntimeError('New content mismatch '+rel)
 for rel in CREATE:
  if digest(safe(ROOT/rel))!=manifest['create'][rel]:raise RuntimeError('New asset mismatch '+rel)
 print('ZOMOROD_ONEPASS_THREE_ROTATING_ROWS_LOGO_GLOBAL_SEARCH_LANGUAGES=VERIFIED')
 print('ZOMOROD_ONEPASS_UNTOUCHED_INNER_FILES=VERIFIED')

def restore(dir,manifest,old):
 # Never clobber a concurrent edit (fail closed).
 for rel in REPLACE:
  path=ROOT/rel;digest_now=digest(safe(path));details=manifest['replace'][rel]
  if digest_now==details['after']:atomic(path,old[rel],details['mode'])
  elif digest_now!=details['before']:raise RuntimeError('Concurrent edit, refuse restore '+rel)
 for rel in CREATE:
  path=ROOT/rel
  if path.exists():
   if path.is_symlink() or digest(safe(path))!=manifest['create'][rel]:
    raise RuntimeError('Concurrent create edit, refuse removal '+rel)
   path.unlink()
 ensure_unchanged(manifest)

def apply(run):
 with lock():
  manifest=preflight();dir=key(run)
  if dir.exists() or dir.is_symlink():raise RuntimeError('Release already exists')
  dir.mkdir(parents=True,mode=0o700)
  prev,new=candidates()
  for rel in REPLACE:
   target=dir/'old'/rel;target.parent.mkdir(parents=True,exist_ok=True)
   atomic(target,prev[rel],0o600)
   if digest(safe(target))!=manifest['replace'][rel]['before']:raise RuntimeError('Backup copy not exact')
  atomic(dir/'manifest.json',json.dumps(manifest,sort_keys=True).encode(),0o600)
  for rel in REPLACE:
   if digest(safe(ROOT/rel))!=manifest['replace'][rel]['before']:raise RuntimeError('Live revision changed during backup')
  try:
   for rel in CREATE:atomic(ROOT/rel,new[rel],0o644)
   for rel in ('assets/zm-reference-v3.js','assets/zm-reference-v3.css','index.html'):
    if digest(safe(ROOT/rel))!=manifest['replace'][rel]['before']:raise RuntimeError('Concurrent modification '+rel)
    atomic(ROOT/rel,new[rel],manifest['replace'][rel]['mode'])
   verify(run)
  except BaseException:
   restore(dir,manifest,prev)
   raise
  print('ZOMOROD_ONEPASS_APPLIED_NEW_CONTENT=YES')

def rollback(run):
 with lock():
  root_guard();dir,manifest,old=load(run)
  restore(dir,manifest,old)
  print('ZOMOROD_ONEPASS_EXACT_BASELINE_RESTORED=YES')

def main():
 if len(sys.argv)==2 and sys.argv[1]=='check':print(json.dumps(preflight(),sort_keys=True))
 elif len(sys.argv)==3 and sys.argv[1] in ('apply','verify','rollback'):
  {'apply':apply,'verify':verify,'rollback':rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit('Usage: check | apply RUN | verify RUN | rollback RUN')
if __name__=='__main__':main()