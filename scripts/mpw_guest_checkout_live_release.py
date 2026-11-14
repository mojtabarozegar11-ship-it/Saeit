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


def has_buyer_email_form(markup, expected_action=None, action_prefix=None,
                         require_csrf=False, require_source_csrf=False):
 """Conservative same-form check, not proof of email ownership or live settlement."""
 if type(markup) is not str or len(markup)>180000:
  return False

 class InvoiceFormParser(HTMLParser):
  _VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
  _INERT={'script','style','textarea','template','noscript'}
  def __init__(self):
   super().__init__(convert_charrefs=True)
   self.forms=[]
   self.matches=0
   self.malformed=False

  @staticmethod
  def _concealed(tag,attributes):
   style=re.sub(r'\s+','',str(attributes.get('style') or '').lower())
   return (tag in InvoiceFormParser._INERT or 'hidden' in attributes
      or 'inert' in attributes
      or str(attributes.get('aria-hidden') or '').lower()=='true'
      or 'display:none' in style or 'visibility:hidden' in style
      or 'opacity:0' in style)

  def _accessible(self):
   return self.forms and not any(h or d for _,h,d in self.forms[-1]['parents'])

  def handle_starttag(self,tag,attrs):
   keys=[k for k,_ in attrs]
   attributes=dict(attrs)
   if tag=='form':
    if self.forms:
     self.forms[-1]['valid']=False
     self.malformed=True
    method=str(attributes.get('method') or '').lower()
    action=str(attributes.get('action') or '')
    template_pattern=(r'/commerce/trx-easy/start/'
                      r'(?:[1-9][0-9]*|\{\{\s*product\.(?:pk|id)\s*\}\})/')
    rendered_pattern=r'/commerce/trx-easy/start/[1-9][0-9]*/'
    valid=(method=='post' and re.fullmatch(template_pattern if require_source_csrf else rendered_pattern,action) is not None
       and (expected_action is None or expected_action==action)
       and (action_prefix is None or action.startswith(action_prefix))
       and len(keys)==len(set(keys)))
    self.forms.append({'valid':valid,'email':0,'csrf':0,'source_csrf':0,'parents':[]})
   elif self.forms:
    form=self.forms[-1]
    if tag not in self._VOID:
     form['parents'].append((tag,self._concealed(tag,attributes),tag=='fieldset' and 'disabled' in attributes))
    if tag=='input':
     accessible=self._accessible()
     if attributes.get('name')=='csrfmiddlewaretoken':
      value=str(attributes.get('value') or '')
      ok=(str(attributes.get('type') or '').lower()=='hidden'
          and 'disabled' not in attributes and accessible
          and 32<=len(value)<=128 and value.isascii() and value.isalnum()
          and len(keys)==len(set(keys)))
      form['csrf']+=1 if ok else 2
     if attributes.get('name')=='email':
      ok=(str(attributes.get('type') or '').lower()=='email'
          and 'required' in attributes and 'disabled' not in attributes
          and 'readonly' not in attributes and 'hidden' not in attributes
          and 'inert' not in attributes and accessible
          and not self._concealed(tag,attributes)
          and len(keys)==len(set(keys)))
      form['email']+=1 if ok else 2

  def handle_data(self,data):
   if self.forms and self._accessible() and re.search(r'{%\s*csrf_token\s*%}',data):
    self.forms[-1]['source_csrf']+=len(re.findall(r'{%\s*csrf_token\s*%}',data))

  def handle_endtag(self,tag):
   if not self.forms:
    return
   if tag=='form':
    form=self.forms.pop()
    if form['parents']:
     form['valid']=False
    if (form['valid'] and form['email']==1
       and (not require_csrf or form['csrf']==1)
       and (not require_source_csrf or form['source_csrf']==1)):
     self.matches+=1
   else:
    parents=self.forms[-1]['parents']
    if parents and parents[-1][0]==tag:
     parents.pop()
    elif any(t==tag for t,_,_ in parents):
     self.forms[-1]['valid']=False

 parser=InvoiceFormParser()
 parser.feed(markup)
 parser.close()
 return parser.matches==1 and not parser.malformed and not parser.forms

def preflight_checkout_email_template():
 """Fail before any production write if buyer form or CSRF is absent."""
 path=APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
 if path.is_symlink() or not path.is_file() or not path.is_relative_to(APP):
  fail('CHECKOUT_TEMPLATE_MISSING_OR_UNSAFE')
 try:
  root=APP.resolve(strict=True)
  parent=path.parent
  while parent!=APP:
   if parent.is_symlink():
    fail('CHECKOUT_TEMPLATE_PARENT_SYMLINK')
   parent=parent.parent
  if not path.resolve(strict=True).is_relative_to(root):
   fail('CHECKOUT_TEMPLATE_OUTSIDE_APP')
  if path.stat().st_size>180000:
   fail('CHECKOUT_TEMPLATE_OVERSIZE')
  raw=path.read_bytes()
  if len(raw)>180000:
   fail('CHECKOUT_TEMPLATE_OVERSIZE')
  markup=raw.decode('utf8')
 except (OSError,UnicodeError,RuntimeError) as exc:
  if isinstance(exc,RuntimeError):
   raise
  fail('CHECKOUT_TEMPLATE_UNREADABLE:'+type(exc).__name__)
 if not has_buyer_email_form(markup,
      action_prefix='/commerce/trx-easy/start/',require_source_csrf=True):
  fail('GUEST_EMAIL_TEMPLATE_CONTRACT_MISSING')
 return digest(raw)


def guard():
 if pwd.getpwuid(os.geteuid()).pw_name!='zomorod2': fail('WRONG_ACCOUNT')
 for p in (APP,PUBLIC):
  if p.is_symlink() or not p.is_dir() or p.resolve()!=p: fail('UNSAFE_ROOT:'+str(p))
 wsgi=PUBLIC/'passenger_wsgi.py'
 if wsgi.is_symlink() or not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text('utf8','replace'):
  fail('PASSENGER_APP_MISMATCH')
 # PassengerAppRoot is the actual web process root, distinct from Django source.
 # Reject deployment if cPanel's public .htaccess changes or goes missing.
 htaccess=PUBLIC/'.htaccess'
 if htaccess.is_symlink() or not htaccess.is_file() or htaccess.stat().st_size>100000:
  fail('PASSENGER_ROOT_DIRECTIVE_UNSAFE')
 roots=re.findall(r'(?im)^\s*PassengerAppRoot\s+([^\r\n#]+)',htaccess.read_text('utf8','replace'))
 if len(roots)!=1 or roots[0].strip().strip('"').strip("'").rstrip('/') not in (str(PUBLIC),'mojplaywin.com'):
  fail('PASSENGER_REGISTERED_ROOT_MISMATCH')
 marker=PUBLIC/'tmp/restart.txt'
 if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
  fail('UNSAFE_PASSENGER_RESTART_TARGET')
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
  # Restrict this upgrade to the exact live version installed by successful run 41120996466.
  if digest(installed)!='7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f':
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
 # cPanel .htaccess registers PUBLIC as PassengerAppRoot. Touching APP/tmp
 # does not restart public workers, leaving the old guest handler live (404).
 marker=PUBLIC/'tmp/restart.txt'
 if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
  fail('UNSAFE_PASSENGER_RESTART_MARKER')
 marker.touch()

def publish(run,src_path):
 guard();src=source_from(src_path);old,new,needed=plan(src)
 template_sha=preflight_checkout_email_template()
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
 # Recheck source exactly before any file mutation: fail closed on template drift.
 if preflight_checkout_email_template()!=template_sha:
  fail('CHECKOUT_TEMPLATE_CHANGED_DURING_RELEASE')
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

def publish_onefile(run,src_path):
 guard()
 live=TARGETS['guest']
 expected='7693254e4ed72141b6de7fc283c5a3214159ea49d838318337e47e86953f5f2f'
 if live.is_symlink() or not live.is_file() or digest(live.read_bytes())!=expected:
  fail('ONE_FILE_EXACT_OLD_SHA_REQUIRED')
 old,new,needed=plan(source_from(src_path))
 if not needed or any(new[k]!=old[k] for k in ('pages','web')):
  fail('ONE_FILE_ONLY_PLAN_REQUIRED')
 publish(run,src_path)

def preview(src_path):
 guard();src=source_from(src_path);old,new,needed=plan(src)
 preflight_checkout_email_template()
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
  if not has_buyer_email_form(body,expected_action=f'/commerce/trx-easy/start/{pid}/',
                              require_csrf=True):
   fail('GUEST_EMAIL_OR_CSRF_POST_FORM_MISSING:'+str(pid))
  print('MPW_GUEST_CHECKOUT_ROUTE='+json.dumps({'product':pid,'http':response.status_code,'handler':getattr(target,'__name__','?'),'order_created':False}))
 recovery_route = '/commerce/trx-easy/purchases/'
 try:
  handler = resolve(recovery_route).func
 except Exception:
  fail('PURCHASES_ROUTE_UNRESOLVED')
 recovery = Client(enforce_csrf_checks=True).get(
  recovery_route, secure=True, HTTP_HOST='mojplaywin.com')
 if recovery.status_code != 200:
  fail('ANONYMOUS_PURCHASES_HTTP:'+str(recovery.status_code))
 if b'No active purchase session' not in recovery.content:
  fail('PURCHASES_SAFE_RECOVERY_BODY_MISSING')
 if recovery.headers.get('X-Robots-Tag') != 'noindex, nofollow':
  fail('PURCHASES_NOINDEX_MISSING')
 if 'no-store' not in recovery.headers.get('Cache-Control',''):
  fail('PURCHASES_NOSTORE_MISSING')
 print('MPW_GUEST_PURCHASES_ROUTE='+json.dumps({
  'http': recovery.status_code, 'handler': getattr(handler,'__name__','?'),
  'anonymous': True, 'order_created': False, 'payment_created': False}))
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
 elif len(sys.argv)==4 and sys.argv[1]=='publish-onefile': publish_onefile(sys.argv[2],sys.argv[3])
 elif len(sys.argv)==2 and sys.argv[1]=='verify': verify()
 elif len(sys.argv)==3 and sys.argv[1]=='rollback': rollback(sys.argv[2])
 else: raise SystemExit('preview GUEST_MODULE | publish-onefile RUN_ID GUEST_MODULE | verify | rollback RUN_ID')
