#!/usr/bin/env python3
"""Zomorod VISION v3: three-file immutable-baseline, rollback-safe homepage repair.
Never alter shared templates, site directories, image assets, .htaccess or data.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

SITE=Path('/home/zomorod2/public_html')
STAGE=Path(__file__).resolve().parent
BACKUPS=Path('/home/zomorod2/.backups/zomorod-vision-ux-20261113')
LOCK=BACKUPS.parent/'.zomorod-homepage-deploy.lock'
FILES={
 'index.html':SITE/'index.html',
 'assets/zm-reference-v3.css':SITE/'assets/zm-reference-v3.css',
 'assets/zm-reference-v3.js':SITE/'assets/zm-reference-v3.js'
}
ORIGINAL_ARCHIVE=SITE/'site-heritage/home-before-nexus-20261112/index.html'
PROTECTED=(
 'agriculture/index.html','research/index.html','industry/index.html',
 'company/index.html','services/index.html','contact/index.html',
 'store/index.php','sitemap.xml','.htaccess','games/index.html',
 'apps/index.html','auctions/index.html'
)

def sha(data:bytes)->str:
 return hashlib.sha256(data).hexdigest()

def read_safe(path:Path)->bytes:
 if path.is_symlink() or not path.is_file():raise RuntimeError('Missing or symlinked file: '+str(path))
 return path.read_bytes()

def validate_id(run:str)->Path:
 if not re.fullmatch(r'ux-[0-9]{1,20}',run):raise RuntimeError('Invalid release id')
 return BACKUPS/run

def identity():
 if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2':raise RuntimeError('Unexpected system account')
 for p in (SITE,SITE/'assets',STAGE,BACKUPS.parent):
  if not p.is_dir() or p.is_symlink():raise RuntimeError('Unsafe directory: '+str(p))
 if BACKUPS.is_symlink() or LOCK.is_symlink():raise RuntimeError('Unsafe backup location')

def protected():
 out={}
 for name in PROTECTED:
  path=SITE/name
  if path.exists():out[name]=sha(read_safe(path))
 if len(out)<9:raise RuntimeError('Too few protected files')
 return out

def candidate():
 out={}
 for path in FILES:
  old=read_safe(STAGE/'old'/path)
  new=read_safe(STAGE/'new'/path)
  if old==new:raise RuntimeError('No new content for '+path)
  out[path]={'old':old,'new':new}
 index=out['index.html']['new']
 if b'<body class="zm-vision-v3">' not in index:raise RuntimeError('Unexpected homepage class')
 if b'zm-reference-v3.css?v=20261113-ux1' not in index or b'zm-reference-v3.js?v=20261113-ux1' not in index:raise RuntimeError('No cache bust marker')
 if b'\"/economy/\"' not in index or b'\"/news/\"' not in index:raise RuntimeError('Navigation correction absent')
 for forbidden in ('ونکوور','Vancouver','ISO 9001','ISO 14001'):
  if forbidden.encode('utf-8') in index:raise RuntimeError('Unverified assertion present')
 js=out['assets/zm-reference-v3.js']['new']
 if not all(v in js for v in (b"search-found",b"aria-pressed",b"scrollBy",b"next")):raise RuntimeError('Expected functional JS absent')
 if b'.skip-link:focus' not in out['assets/zm-reference-v3.css']['new']:raise RuntimeError('Access CSS absent')
 return out

def preflight():
 identity()
 c=candidate()
 if not ORIGINAL_ARCHIVE.is_file() or ORIGINAL_ARCHIVE.is_symlink():raise RuntimeError('Archived predecessor missing')
 for rel,versions in c.items():
  if sha(read_safe(FILES[rel]))!=sha(versions['old']):
   raise RuntimeError('Live revision changed: '+rel)
 return {'files':{rel:{'old':sha(v['old']),'new':sha(v['new']),'mode':stat.S_IMODE(FILES[rel].stat().st_mode)} for rel,v in c.items()},
         'protected':protected(),'archived':sha(read_safe(ORIGINAL_ARCHIVE))}

def atomic(dst:Path,blob:bytes,mode:int):
 temporary=None
 try:
  with tempfile.NamedTemporaryFile(prefix='.zm-vision-ux-',dir=dst.parent,delete=False) as f:
   temporary=Path(f.name)
   f.write(blob);f.flush();os.fsync(f.fileno())
  os.chmod(temporary,mode)
  os.replace(temporary,dst)
 finally:
  if temporary and temporary.exists():temporary.unlink()

@contextmanager
def lock():
 with open(LOCK,'a+b') as handle:
  fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

def verify(run):
 identity()
 folder=validate_id(run)
 manifest=json.loads(read_safe(folder/'manifest.json').decode('utf-8'))
 for rel,entry in manifest['files'].items():
  if sha(read_safe(folder/'old'/rel))!=entry['old']:raise RuntimeError('Original backup differs')
  if sha(read_safe(FILES[rel]))!=entry['new']:raise RuntimeError('Installed file mismatch: '+rel)
 if protected()!=manifest['protected']:raise RuntimeError('Protected files changed')
 if sha(read_safe(ORIGINAL_ARCHIVE))!=manifest['archived']:raise RuntimeError('Historic backup modified')
 print('VISION_UX_HOME_CSS_JS_VERIFIED=YES')
 print('VISION_UX_INTERNAL_FILES_UNCHANGED=YES')

def revert_partial(manifest,folder):
 for rel in ('index.html','assets/zm-reference-v3.css','assets/zm-reference-v3.js'):
  meta=manifest['files'][rel]
  existing=sha(read_safe(FILES[rel]))
  if existing==meta['new']:
   atomic(FILES[rel],read_safe(folder/'old'/rel),meta['mode'])
  elif existing!=meta['old']:raise RuntimeError('Concurrent change detected; halt rollback '+rel)
 if protected()!=manifest['protected']:raise RuntimeError('Protected files changed after restore')

def apply(run):
 with lock():
  manifest=preflight()
  folder=validate_id(run)
  if folder.exists() or folder.is_symlink():raise RuntimeError('Release backup already exists')
  folder.mkdir(parents=True,mode=0o700)
  for rel in FILES:
   saved=folder/'old'/rel
   saved.parent.mkdir(exist_ok=True,parents=True)
   atomic(saved,read_safe(FILES[rel]),0o600)
   if sha(read_safe(saved))!=manifest['files'][rel]['old']:raise RuntimeError('Backup checksum mismatch')
  (folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,ensure_ascii=False),encoding='utf-8')
  c=candidate()
  try:
   for rel in ('assets/zm-reference-v3.js','assets/zm-reference-v3.css','index.html'):
    meta=manifest['files'][rel]
    if sha(read_safe(FILES[rel]))!=meta['old']:raise RuntimeError('Concurrent change before install')
    atomic(FILES[rel],c[rel]['new'],meta['mode'])
   verify(run)
  except BaseException:
   revert_partial(manifest,folder)
   raise
  print('VISION_UX_3_FILES_UPDATED=YES')
  print('VISION_UX_PROTECTED_FILES_UNCHANGED=YES')

def rollback(run):
 with lock():
  identity()
  folder=validate_id(run)
  manifest=json.loads(read_safe(folder/'manifest.json').decode('utf-8'))
  if sha(read_safe(ORIGINAL_ARCHIVE))!=manifest['archived']:raise RuntimeError('Historical original altered')
  revert_partial(manifest,folder)
  for rel in FILES:
   assert sha(read_safe(FILES[rel]))==manifest['files'][rel]['old']
  print('VISION_UX_EXACT_ORIGINAL_RESTORED=YES')

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('action',choices=('check','apply','verify','rollback'))
 parser.add_argument('run',nargs='?')
 args=parser.parse_args()
 if args.action=='check':print(json.dumps(preflight(),sort_keys=True))
 else:
  if not args.run:parser.error('release id needed')
  {'apply':apply,'verify':verify,'rollback':rollback}[args.action](args.run)

if __name__=='__main__':main()
