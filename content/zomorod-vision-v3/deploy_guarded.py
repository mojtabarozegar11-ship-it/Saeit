#!/usr/bin/env python3
"""Sha-guarded production release for Zomorod Mellal VISION v3.

Owner-approved design reference -> real HTML/CSS/JS and decorative artwork.
Scope limited to /index.html, one new CSS, one new JS, and new art directory.
Preserves all existing internal pages, scripts, databases, NEXUS assets, .htaccess.
Requires user identity and byte-exact live SHA before ANY write.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import io
import json
import os
import pwd
import re
import shutil
import stat
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path

SITE = Path('/home/zomorod2/public_html')
SRC = Path(__file__).resolve().parent
BACKUPS = Path('/home/zomorod2/.backups/zomorod-vision-v3')
LOCK = BACKUPS.parent/'.zomorod-homepage-deploy.lock'
HOME = SITE/'index.html'
CSS = SITE/'assets/zm-reference-v3.css'
JS = SITE/'assets/zm-reference-v3.js'
ART = SITE/'assets/zm-vision-v3/art'
OLD_ARCHIVE = SITE/'site-heritage/home-before-nexus-20261112/index.html'
EXPECTED_CURRENT_SHA = '0eca61aa473b46dc5556298b96b0b2d6fb47e29aa111b93f83f2405747491af9'
EXPECTED_ARCHIVE_SHA = '99e9c38cd20aaf400a3c68c2064211dc48d4ff0e518ee4815061ea0ca2626edc'
PROTECTED = (
 'agriculture/index.html','research/index.html','industry/index.html',
 'company/index.html','services/index.html','contact/index.html',
 'store/index.php','sitemap.xml','.htaccess','games/index.html',
 'apps/index.html','auctions/index.html',
)
EXPECTED_ART = {
 'hero.webp','farming.webp','genetics.webp','industry.webp','economy.webp',
 'greenhouse.webp','livestock.webp','lab.webp','innovation.webp','books.webp',
 'castle.webp','coins.webp','globe-trade.webp','robot.webp','research-book.webp',
 'tools.webp','letter.webp',
}

def sha(blob: bytes)->str:
 return hashlib.sha256(blob).hexdigest()

def safe_file(p:Path)->bytes:
 if p.is_symlink() or not p.is_file():
  raise RuntimeError('Missing or symlinked protected file: '+str(p))
 return p.read_bytes()

def identity():
 if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2':
  raise RuntimeError('Refusing unexpected host account')
 for p in (SITE,SRC,BACKUPS.parent,SITE/'assets'):
  if not p.is_dir() or p.is_symlink():
   raise RuntimeError('Refusing unexpected directory: '+str(p))
 if BACKUPS.is_symlink() or ART.parent.is_symlink():
  raise RuntimeError('Symlink in destination')


def candidate()->dict:
 d={
 'html':safe_file(SRC/'index.html'),
 'css':safe_file(SRC/'assets/zm-reference-v3.css'),
 'js':safe_file(SRC/'assets/zm-reference-v3.js'),
 'zip':safe_file(SRC/'artwork.zip'),
 }
 if not (24000<=len(d['html'])<=60000 and 22000<=len(d['css'])<=80000 and 2000<=len(d['js'])<=20000):
  raise RuntimeError('Unexpected candidate size')
 if b'<body class="zm-vision-v3">' not in d['html']:
  raise RuntimeError('Not the approved page implementation')
 if b'/assets/zm-reference-v3.css' not in d['html'] or b'/assets/zm-reference-v3.js' not in d['html']:
  raise RuntimeError('Missing versioned CSS/JS')
 for forbidden in ('Vancouver','ونکوور','ISO 9001','ISO 14001','ISO 22000'):
  if forbidden.encode() in d['html']:
   raise RuntimeError('Forbidden unverified company assertion')
 if b'prefers-reduced-motion' not in d['css'] or b'@media(max-width:640px)' not in d['css']:
  raise RuntimeError('Missing accessibility or mobile CSS')
 with zipfile.ZipFile(io.BytesIO(d['zip'])) as z:
  names=z.namelist()
  if set(names)!={'art/'+x for x in EXPECTED_ART}:
   raise RuntimeError('Unexpected artwork ZIP contents')
  if any(z.getinfo(name).file_size<=100 or z.getinfo(name).file_size>100000 for name in names):
   raise RuntimeError('Invalid art file size')
  d['art']={name.split('/')[-1]:z.read(name) for name in names}
  if not all(blob[:4]==b'RIFF' and blob[8:12]==b'WEBP' for blob in d['art'].values()):
   raise RuntimeError('Non-WEBP art payload')
 return d

def protected_hashes()->dict:
 out={}
 for path in PROTECTED:
  p=SITE/path
  if p.exists():out[path]=sha(safe_file(p))
 if len(out)<9:
  raise RuntimeError('Insufficient original site protection evidence')
 return out

def preflight()->dict:
 identity()
 d=candidate()
 original=safe_file(HOME)
 if sha(original)!=EXPECTED_CURRENT_SHA or b'<body class="nexus-home">' not in original:
  raise RuntimeError('Live homepage changed: fail closed')
 if sha(safe_file(OLD_ARCHIVE))!=EXPECTED_ARCHIVE_SHA:
  raise RuntimeError('Preserved historical page changed: fail closed')
 for p in (CSS,JS,ART,ART.parent):
  if p.exists() or p.is_symlink():
   raise RuntimeError('New version path already occupied: '+str(p))
 for img in ('static/site/zomorod-v7/company-logo.webp','static/site/heroes/ai.webp'):
  safe_file(SITE/img)
 return {'original':sha(original),'candidate':sha(d['html']),'css':sha(d['css']),'js':sha(d['js']),
         'art':{name:sha(blob) for name,blob in d['art'].items()},'protected':protected_hashes(),
         'bytes':{'old':len(original),'new':len(d['html']),'artzip':len(d['zip'])}}

def atomic(path:Path,data:bytes,mode:int=0o644):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-vision-write-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode)
  os.replace(temp,path)
 finally:
  if temp and temp.exists():temp.unlink()

@contextmanager
def locked():
 with open(LOCK,'a+b') as f:
  fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:yield
  finally:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def release_folder(run:str)->Path:
 if not re.fullmatch(r'vision-[0-9]{1,20}',run):
  raise RuntimeError('Invalid release id')
 return BACKUPS/run

def apply(run:str):
 with locked():
  b=preflight();d=candidate();original=HOME.read_bytes()
  folder=release_folder(run)
  if folder.exists() or folder.is_symlink():raise RuntimeError('Release exists')
  folder.mkdir(parents=True,mode=0o700)
  mode=stat.S_IMODE(HOME.stat().st_mode)
  atomic(folder/'home.before.html',original,0o600)
  if sha(safe_file(folder/'home.before.html'))!=b['original']:raise RuntimeError('Backup not safe')
  manifest=dict(b,home_mode=mode)
  (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True),encoding='utf-8')
  tmpart=SITE/'assets'/('.zm-vision-staging-'+run)
  artdir_created=False;css_created=False;js_created=False;home_changed=False
  try:
   if tmpart.exists():raise RuntimeError('Art staging occupied')
   tmpart.mkdir(mode=0o700)
   for name,blob in d['art'].items():atomic(tmpart/name,blob,0o644)
   if {p.name:sha(p.read_bytes()) for p in tmpart.iterdir()}!=b['art']:
    raise RuntimeError('Artwork stage checksum mismatch')
   ART.parent.mkdir(mode=0o755)
   os.rename(tmpart,ART)
   artdir_created=True
   atomic(CSS,d['css']);css_created=True
   atomic(JS,d['js']);js_created=True
   if sha(HOME.read_bytes())!=b['original']:
    raise RuntimeError('Concurrent page changed before install')
   atomic(HOME,d['html'],mode);home_changed=True
   verify(run)
  except BaseException:
   if home_changed and sha(HOME.read_bytes())==b['candidate']:
    atomic(HOME,original,mode)
   if css_created and CSS.is_file() and sha(CSS.read_bytes())==b['css']:
    CSS.unlink()
   if js_created and JS.is_file() and sha(JS.read_bytes())==b['js']:
    JS.unlink()
   if artdir_created and ART.is_dir() and {p.name:sha(p.read_bytes()) for p in ART.iterdir()}==b['art']:
    shutil.rmtree(ART)
   if ART.parent.is_dir() and not any(ART.parent.iterdir()):ART.parent.rmdir()
   if tmpart.is_dir():shutil.rmtree(tmpart)
   raise
  print('VISION_V3_HOME_APPLIED=YES')
  print('VISION_V3_ART_FILES='+str(len(b['art'])))
  print('VISION_V3_PROTECTED_UNCHANGED=YES')

def verify(run:str):
 folder=release_folder(run)
 b=json.loads(safe_file(folder/'manifest.json').decode())
 if sha(safe_file(folder/'home.before.html'))!=b['original']:
  raise RuntimeError('Original backup corrupt')
 for path,digest in ((HOME,b['candidate']),(CSS,b['css']),(JS,b['js']),(OLD_ARCHIVE,EXPECTED_ARCHIVE_SHA)):
  if sha(safe_file(path))!=digest:
   raise RuntimeError('Installed file hash mismatch: '+str(path))
 if not ART.is_dir() or ART.is_symlink():raise RuntimeError('Artwork folder missing')
 current={p.name:sha(safe_file(p)) for p in ART.iterdir()}
 if current!=b['art']:raise RuntimeError('Artwork hash mismatch')
 for rel,digest in b['protected'].items():
  if sha(safe_file(SITE/rel))!=digest:
   raise RuntimeError('Protected source changed: '+rel)
 print('VISION_V3_RELEASE_CHECKSUMS=VERIFIED')
 print('VISION_V3_INNER_FILES=UNCHANGED')

def rollback(run:str):
 with locked():
  identity()
  folder=release_folder(run)
  b=json.loads(safe_file(folder/'manifest.json').decode())
  original=safe_file(folder/'home.before.html')
  if sha(original)!=b['original']:raise RuntimeError('Original backup mismatch')
  current=sha(safe_file(HOME))
  if current not in (b['candidate'],b['original']):
   raise RuntimeError('Concurrent homepage update: refuse rollback')
  if current==b['candidate']:
   atomic(HOME,original,b['home_mode'])
  for path,digest in ((CSS,b['css']),(JS,b['js'])):
   if path.is_file():
    if sha(path.read_bytes())!=digest:raise RuntimeError('Asset changed; refuse cleanup')
    path.unlink()
  if ART.is_dir():
   actual={p.name:sha(safe_file(p)) for p in ART.iterdir()}
   if actual!=b['art']:raise RuntimeError('Art updated; refuse cleanup')
   shutil.rmtree(ART)
  if ART.parent.is_dir() and not any(ART.parent.iterdir()):ART.parent.rmdir()
  for rel,digest in b['protected'].items():
   if sha(safe_file(SITE/rel))!=digest:raise RuntimeError('Protected page mismatch after rollback')
  assert sha(HOME.read_bytes())==b['original']
  print('VISION_V3_ORIGINAL_HOME_RESTORED=YES')

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('command',choices=['check','apply','verify','rollback'])
 parser.add_argument('run',nargs='?')
 args=parser.parse_args()
 if args.command=='check':print(json.dumps(preflight(),ensure_ascii=False,sort_keys=True))
 else:
  if not args.run:parser.error('Release id required')
  {'apply':apply,'verify':verify,'rollback':rollback}[args.command](args.run)

if __name__=='__main__':main()