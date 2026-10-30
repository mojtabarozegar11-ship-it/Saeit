#!/usr/bin/env python3
"""Atomic MojPlayWin guest TRX checkout release with exact rollback."""
from __future__ import annotations
import hashlib, json, os, pwd, re, shutil, stat, sys, tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
PUBLIC=Path('/home/zomorod2/mojplaywin.com')
BACKUPS=Path('/home/zomorod2/.local/share/mpw-guest-checkout-release')
TARGETS={
 'guest':APP/'services/mpw_trx_guest_commerce.py',
 'pages':APP/'services/mpw_trx_public_pages.py',
 'web':APP/'services/mpw_trx_commercial_web.py',
}
MARKERS={
 'pages':'# MPW_GUEST_CHECKOUT_LIVE_V1',
 'web':'# MPW_GUEST_CHECKOUT_LIVE_V1',
}
IMPORT='from services.mpw_trx_guest_commerce import patch_{kind} as _mpw_patch_{kind}\n_mpw_patch_{kind}(globals())\n'

def digest(b): return hashlib.sha256(b).hexdigest()
def fail(s): raise RuntimeError('MPW_GUEST_RELEASE_ABORT: '+s)
def guard():
 if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2': fail('WRONG_ACCOUNT')
 for p in (APP,PUBLIC):
  if p.is_symlink() or not p.is_dir() or p.resolve()!=p: fail('UNSAFE_ROOT:'+str(p))
 wsgi=PUBLIC/'passenger_wsgi.py'
 if wsgi.is_symlink() or not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text('utf8','replace'):
  fail('PASSENGER_APP_MISMATCH')
 for p in (APP/'tmp/restart.txt',):
  if p.is_symlink() or not p.parent.is_dir(): fail('UNSAFE_RESTART_TARGET')
 for key in ('pages','web'):
  p=TARGETS[key]
  if p.is_symlink() or not p.is_file() or p.parent.is_symlink() or APP not in p.parents: fail('UNSAFE_TARGET:'+key)

def source_from(path):
 p=Path(path)
 if p.is_symlink() or not p.is_file(): fail('GUEST_SOURCE_MISSING')
 raw=p.read_bytes()
 if len(raw)>60000: fail('GUEST_SOURCE_SIZE')
 compile(raw.decode('utf8'),str(p),'exec')
 if b'def patch_public(namespace):' not in raw or b'def patch_commercial(namespace):' not in raw: fail('GUEST_SOURCE_CONTRACT')
 return raw

def plan(src):
 old={k:p.read_bytes() for k,p in TARGETS.items() if k!='guest'}
 if any(MARKERS[k] in old[k].decode('utf8','replace') for k in MARKERS):
  if not all(MARKERS[k] in old[k].decode('utf8','replace') for k in MARKERS):
   fail('PARTIAL_GUEST_RELEASE')
  for key in ('pages','web'):
   body=old[key].decode('utf8')
   if body.count(MARKERS[key])!=1 or IMPORT.format(kind='public' if key=='pages' else 'commercial') not in body:
    fail('GUEST_HOOK_DRIFT:'+key)
  live=TARGETS['guest']
  if live.is_symlink() or not live.is_file(): fail('GUEST_MODULE_MISSING')
  installed=source_from(live)
  if installed==src: return old,old,False
  # Restrict the first upgrade to the exact version installed in successful run 41109493749.
  if digest(installed)!='0db371611ef61b052e368505297af0808cb0108e56c5d99a9f11f66338da19ba':
   fail('UNRECOGNIZED_GUEST_UPGRADE_BASE')
  return old,old,True
 # A module without both verified caller hooks is never safe to overwrite.
 if TARGETS['guest'].exists() or TARGETS['guest'].is_symlink():
  fail('GUEST_MODULE_COLLISION')
 new={}
 for key,raw in old.items():
  text=raw.decode('utf8')
  if key=='pages':
   if text.count('def product_checkout(request, product_id):')!=1 or text.count('def purchases(request):')!=1: fail('BUYER_ROUTE_DRIFT')
   line=IMPORT.format(kind='public')
  else:
   if text.count('def _views():')!=1 or 'COMMERCIAL_URLPATTERNS=' not in text: fail('COMMERCIAL_ROUTE_DRIFT')
   line=IMPORT.format(kind='commercial')
  new[key]=(text+'\n'+MARKERS[key]+'\n'+line).encode('utf8')
  compile(new[key].decode('utf8'),key,'exec')
 # The live invoice, reconciliation, order, finality and download functions stay in place.
 for key in ('web','pages'):
  before=old[key].decode('utf8'); after=new[key].decode('utf8')
  if before not in after: fail('UNRELATED_SOURCE_CHANGE:'+key)
 return old,new,True

def private_backup(run):
 if not re.fullmatch(r'[0-9]{8,20}',run): fail('INVALID_RUN_ID')
 BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
 if BACKUPS.is_symlink() or stat.S_IMODE(BACKUPS.stat().st_mode)&0o077: fail('UNSAFE_BACKUP_DIR')
 d=BACKUPS/run
 if d.exists() or d.is_symlink(): fail('RUN_BACKUP_EXISTS')
 d.mkdir(mode=0o700)
 return d

def atomic(path,raw,expected=None):
 if path.is_symlink(): fail('TARGET_BECAME_SYMLINK')
 if expected is not None and digest(path.read_bytes())!=expected: fail('CONCURRENT_TARGET_EDIT')
 fd,tmp=tempfile.mkstemp(prefix='.mpw-guest-',dir=path.parent)
 try:
  os.fchmod(fd,stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600)
  with os.fdopen(fd,'wb') as f: f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
  dfd=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
  try: os.fsync(dfd)
  finally: os.close(dfd)
 finally:
  if os.path.exists(tmp): os.unlink(tmp)

def restart():
 marker=APP/'tmp/restart.txt'
 if marker.is_symlink(): fail('UNSAFE_RESTART_MARKER')
 marker.touch()

def publish(run,src_path):
 guard();src=source_from(src_path);old,new,needed=plan(src)
 if not needed:
  print('MPW_GUEST_RELEASE=ALREADY_INSTALLED')
  return
 d=private_backup(run)
 before={k:digest(v) for k,v in old.items()}
 after={k:digest(v) for k,v in new.items()}
 for key,raw in old.items():
  with (d/(key+'.bak')).open('xb') as f: os.fchmod(f.fileno(),0o600);f.write(raw);f.flush();os.fsync(f.fileno())
 with (d/'guest.py.bak').open('xb') as f: os.fchmod(f.fileno(),0o600); f.write(TARGETS['guest'].read_bytes() if TARGETS['guest'].exists() else b'')
 manifest={'run':run,'before':before,'after':after,'guest_before':digest(TARGETS['guest'].read_bytes()) if TARGETS['guest'].exists() else None,'guest_after':digest(src)}
 with (d/'manifest.json').open('x') as f: os.fchmod(f.fileno(),0o600);json.dump(manifest,f,sort_keys=True);f.flush();os.fsync(f.fileno())
 changed=[]
 upgrading=manifest['guest_before'] is not None
 try:
  if upgrading:
   atomic(TARGETS['guest'],src,expected=manifest['guest_before']);changed.append('guest')
  else:
   if TARGETS['guest'].exists() or TARGETS['guest'].is_symlink():
    fail('GUEST_MODULE_COLLISION')
   atomic(TARGETS['guest'],src);changed.append('guest')
   for key in ('web','pages'):
    atomic(TARGETS[key],new[key],expected=before[key]);changed.append(key)
  restart()
 except BaseException:
  for key in reversed(changed):
   path=TARGETS[key]
   if key=='guest' and path.is_file() and digest(path.read_bytes())==manifest['guest_after']:
    if upgrading:
     atomic(path,(d/'guest.py.bak').read_bytes(),expected=manifest['guest_after'])
    else: path.unlink()
   elif key!='guest' and path.is_file() and digest(path.read_bytes())==after[key]:
    atomic(path,old[key],expected=after[key])
  restart()
  raise
 print('MPW_GUEST_RELEASE=APPLIED;MODE='+('UPGRADE' if upgrading else 'INSTALL')+
       ';FILES='+('1' if upgrading else '3')+';ORDERS_CREATED=0;PAYMENTS_CREATED=0')

def preview(src_path):
 guard();src=source_from(src_path);old,new,needed=plan(src)
 print('MPW_GUEST_RELEASE_PREFLIGHT='+json.dumps({'needs_install':needed,
  'existing':{k:digest(v) for k,v in old.items()},
  'candidate':{k:digest(v) for k,v in new.items()},
  'source_sha256':digest(src),'orders_created':0,'payments_created':0},sort_keys=True))

def verify():
 guard()
 for key,path in TARGETS.items():
  if path.is_symlink() or not path.is_file(): fail('RELEASE_FILE_MISSING:'+key)
 for key in ('pages','web'):
  text=TARGETS[key].read_text('utf8')
  if MARKERS[key] not in text: fail('RELEASE_PATCH_MISSING:'+key)
 compile(TARGETS['guest'].read_text('utf8'),str(TARGETS['guest']),'exec')
 os.chdir(APP);sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
 import django;django.setup()
 from django.test import Client
 from django.urls import resolve
 for pid in (72,225,879):
  route=f'/store/product/{pid}/checkout/'
  target=resolve(route).func
  response=Client(enforce_csrf_checks=True).get(route,secure=True,HTTP_HOST='mojplaywin.com')
  if response.status_code!=200: fail('ANONYMOUS_CHECKOUT_HTTP:'+str(pid)+':'+str(response.status_code))
  body=response.content.decode('utf8','replace')
  if 'Create invoice and pay with TRX' not in body: fail('TRX_CTA_MISSING:'+str(pid))
  print('MPW_GUEST_CHECKOUT_ROUTE='+json.dumps({'product':pid,'http':response.status_code,'handler':getattr(target,'__name__','?'),'order_created':False}))
 print('MPW_GUEST_RELEASE=VERIFIED;READ_ONLY=TRUE')

def rollback(run):
 guard()
 if not re.fullmatch(r'[0-9]{8,20}',run): fail('INVALID_RUN_ID')
 d=BACKUPS/run
 if d.is_symlink() or not d.is_dir() or (d/'manifest.json').is_symlink(): fail('BACKUP_MISSING')
 meta=json.loads((d/'manifest.json').read_text())
 if meta.get('run')!=run: fail('BACKUP_RUN_MISMATCH')
 for key in ('web','pages'):
  if digest(TARGETS[key].read_bytes())!=meta['after'][key]: fail('ROLLBACK_DRIFT:'+key)
 if digest(TARGETS['guest'].read_bytes())!=meta['guest_after']: fail('ROLLBACK_DRIFT:guest')
 for key in ('web','pages'):
  if meta['after'][key]!=meta['before'][key]:
   backup=(d/(key+'.bak')).read_bytes()
   if digest(backup)!=meta['before'][key]: fail('ROLLBACK_BACKUP_HASH_MISMATCH:'+key)
   atomic(TARGETS[key],backup,expected=meta['after'][key])
 if meta.get('guest_before'):
  backup=(d/'guest.py.bak').read_bytes()
  if digest(backup)!=meta['guest_before']: fail('ROLLBACK_BACKUP_HASH_MISMATCH:guest')
  atomic(TARGETS['guest'],backup,expected=meta['guest_after'])
 else:
  TARGETS['guest'].unlink()
 restart()
 print('MPW_GUEST_RELEASE=ROLLED_BACK;MODE='+('UPGRADE' if meta.get('guest_before') else 'INSTALL'))

if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='preview': preview(sys.argv[2])
 elif len(sys.argv)==4 and sys.argv[1]=='publish': publish(sys.argv[2],sys.argv[3])
 elif len(sys.argv)==2 and sys.argv[1]=='verify': verify()
 elif len(sys.argv)==3 and sys.argv[1]=='rollback': rollback(sys.argv[2])
 else: raise SystemExit('preview GUEST_MODULE | publish RUN_ID GUEST_MODULE | verify | rollback RUN_ID')
