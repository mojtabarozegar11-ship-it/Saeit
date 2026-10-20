#!/usr/bin/env python3
"""MojPlayWin surgical buyer download-path fix: no financial writes or restarts."""
import ast,hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

APP=Path('/home/zomorod2/Saeit-staging')
TARGET=APP/'mpw_commerce/checkout_views.py'
WSGI=Path('/home/zomorod2/mojplaywin.com/passenger_wsgi.py')
BACKUP_DIR=Path('/home/zomorod2/.private_mojplaywin_main_agents')
OLD='''    can_download=False
    if invoice.status==CommerceInvoice.Status.PAID and invoice.order.status=="paid":
        from .entitlements import can_access_purchased_digital_item
        can_download=any(
            can_access_purchased_digital_item(item_id,request.user.pk)
            for item_id in invoice.order.items.values_list("id",flat=True)[:100]
        )
'''
NEW='''    # A verified receipt, ledger entry and entitlement are required for each link.
    verified_download_paths=[]
    if invoice.status==CommerceInvoice.Status.PAID and invoice.order.status=="paid":
        from django.urls import reverse
        from .entitlements import can_access_purchased_digital_item
        for item_id in invoice.order.items.values_list("id",flat=True)[:100]:
            if can_access_purchased_digital_item(item_id,request.user.pk):
                verified_download_paths.append(
                    reverse("mpw_commerce:download",kwargs={"item_id":item_id})
                )
'''
OLD_FIELD='        "can_access_purchased_items":can_download,\n'
NEW_FIELD='''        "can_access_purchased_items":bool(verified_download_paths),
        "download_paths":verified_download_paths,
'''

def digest(b):return hashlib.sha256(b).hexdigest()
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong server account')
 for p in (APP,BACKUP_DIR):
  if p.is_symlink() or not p.is_dir():raise RuntimeError('Unsafe app or backup folder')
 if stat.S_IMODE(BACKUP_DIR.stat().st_mode)&0o077:raise RuntimeError('Backup folder exposed')
 if not TARGET.is_file() or TARGET.is_symlink() or TARGET.parent.is_symlink():raise RuntimeError('Checkout source unsafe')
 if not WSGI.is_file() or WSGI.is_symlink():raise RuntimeError('Passenger mapping not verified')
 if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace'):raise RuntimeError('Unexpected app root')

def changed(raw):
 text=raw.decode('utf8')
 if text.count(OLD)!=1 or text.count(OLD_FIELD)!=1 or '"download_paths":' in text:
  raise RuntimeError('Active checkout version differs: no automatic overwrite')
 updated=text.replace(OLD,NEW,1).replace(OLD_FIELD,NEW_FIELD,1)
 old_tree=ast.parse(text);new_tree=ast.parse(updated)
 def find(tree):
  f=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='checkout_status']
  if len(f)!=1:raise RuntimeError('Status handler not unique')
  return f[0]
 find(old_tree);find(new_tree)
 def remainder(tree):
  return [ast.dump(n,include_attributes=False) for n in tree.body if not(isinstance(n,ast.FunctionDef) and n.name=='checkout_status')]
 if remainder(old_tree)!=remainder(new_tree):raise RuntimeError('Unexpected change outside status handler')
 compile(updated,str(TARGET),'exec')
 return updated.encode('utf8')

def contract(raw):
 """Real Django URL reversal with in-memory simulated paid/unpaid models only."""
 os.chdir(APP);sys.path.insert(0,str(APP))
 os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
 import django
 django.setup()
 from django.contrib.auth.decorators import login_required
 from django.views.decorators.cache import never_cache
 from django.views.decorators.http import require_GET
 from django.http import JsonResponse
 from django.test import RequestFactory
 from django.urls import reverse
 from mpw_commerce.models import CommerceInvoice
 from mpw_commerce import entitlements
 from unittest.mock import patch,Mock
 from types import SimpleNamespace
 root=ast.parse(raw.decode('utf8'))
 fn=next(n for n in root.body if isinstance(n,ast.FunctionDef) and n.name=='checkout_status')
 scope={'__name__':'mpw_commerce.checkout_views','__package__':'mpw_commerce',
  'login_required':login_required,'never_cache':never_cache,'require_GET':require_GET,
  'JsonResponse':JsonResponse,'CommerceInvoice':CommerceInvoice,
  '_ready':lambda request:True,'_deny':lambda:JsonResponse({'error':'Unavailable'},status=404)}
 exec(compile(ast.Module(body=[fn],type_ignores=[]),'<checkout_contract>','exec'),scope)
 view=scope['checkout_status']
 rq=RequestFactory().get('/commerce/checkout/status/123/',secure=True,HTTP_HOST='mojplaywin.com')
 rq.user=SimpleNamespace(is_authenticated=True,is_active=True,pk=-100321)
 fake=Mock()
 fake.filter.return_value.first.return_value=SimpleNamespace(
  status='paid',network='ethereum-mainnet',asset='ETH',
  order=SimpleNamespace(status='paid',items=SimpleNamespace(values_list=lambda *a,**k:[41,42])))
 with patch.object(CommerceInvoice.objects,'select_related',return_value=fake),patch.object(
  entitlements,'can_access_purchased_digital_item',side_effect=lambda item,user:item==41 and user==-100321):
  paid=view(rq,123)
 obj=json.loads(paid.content)
 assert paid.status_code==200 and obj['can_access_purchased_items'] is True,obj
 assert obj['download_paths']==[reverse('mpw_commerce:download',kwargs={'item_id':41})],obj
 assert fake.filter.call_args.kwargs['order__customer_id']==rq.user.pk
 fake.filter.return_value.first.return_value.status='awaiting'
 with patch.object(CommerceInvoice.objects,'select_related',return_value=fake),patch.object(
  entitlements,'can_access_purchased_digital_item',side_effect=AssertionError('No access check for unpaid')):
  unpaid=json.loads(view(rq,123).content)
 assert unpaid['download_paths']==[] and unpaid['can_access_purchased_items'] is False,unpaid
 fake.filter.return_value.first.return_value=None
 with patch.object(CommerceInvoice.objects,'select_related',return_value=fake):
  assert view(rq,123).status_code==404
 print('MPW_STATUS_CONTRACT='+json.dumps({'real_django_url':True,'paid_download_link':True,
  'unpaid_hidden':True,'other_item_hidden':True,'customer_scope':True,'no_payment_created':True}))

def names(run):
 if not re.fullmatch(r'[0-9]{8,20}',run):raise RuntimeError('Invalid release ID')
 return BACKUP_DIR/('mpw-checkout-status-'+run+'.bak'),BACKUP_DIR/('mpw-checkout-status-'+run+'.json')

def atomic(blob):
 fd,tmp=tempfile.mkstemp(dir=TARGET.parent,prefix='.mpw-status-')
 try:
  os.fchmod(fd,stat.S_IMODE(TARGET.stat().st_mode))
  with os.fdopen(fd,'wb') as file:file.write(blob);file.flush();os.fsync(file.fileno())
  os.replace(tmp,TARGET)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def preview():
 guard();before=TARGET.read_bytes();after=changed(before);contract(after)
 print('MPW_STATUS_PREFLIGHT='+json.dumps({'pass':True,'old_sha256':digest(before),
  'new_sha256':digest(after),'changed_file':'mpw_commerce/checkout_views.py','passenger_restart':False}))

def publish(run):
 guard();old=TARGET.read_bytes();new=changed(old);contract(new)
 backup,manifest=names(run)
 if backup.exists() or manifest.exists() or backup.is_symlink() or manifest.is_symlink():raise RuntimeError('Backup collision')
 with backup.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
 info={'run':run,'old':digest(old),'new':digest(new),'file':'mpw_commerce/checkout_views.py'}
 with manifest.open('x',encoding='utf8') as f:os.fchmod(f.fileno(),0o600);json.dump(info,f);f.flush();os.fsync(f.fileno())
 if digest(TARGET.read_bytes())!=info['old']:raise RuntimeError('Concurrent change; no deployment')
 atomic(new)
 if digest(TARGET.read_bytes())!=info['new']:raise RuntimeError('Post-write mismatch')
 print('MPW_STATUS_INSTALLED='+json.dumps({'one_file':info['file'],'no_payment_writes':True,'no_shared_restart':True}))

def verify(run):
 guard();backup,manifest=names(run)
 if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():raise RuntimeError('No backup')
 info=json.loads(manifest.read_text('utf8'))
 if info['run']!=run or digest(backup.read_bytes())!=info['old'] or digest(TARGET.read_bytes())!=info['new']:
  raise RuntimeError('Deployed source differs from pin')
 if digest(changed(backup.read_bytes()))!=info['new']:raise RuntimeError('Unexpected deploy diff')
 contract(TARGET.read_bytes())
 print('MPW_STATUS_VERIFIED=PASS')

def rollback(run):
 guard();backup,manifest=names(run)
 if backup.is_symlink() or manifest.is_symlink() or not backup.is_file() or not manifest.is_file():raise RuntimeError('No rollback backup')
 info=json.loads(manifest.read_text('utf8'))
 old=backup.read_bytes()
 if info['run']!=run or digest(old)!=info['old'] or digest(TARGET.read_bytes())!=info['new']:
  raise RuntimeError('Unexpected concurrent edit; rollback blocked')
 atomic(old)
 assert digest(TARGET.read_bytes())==info['old']
 print('MPW_STATUS_ROLLBACK=PASS')

def selftest():
 assert NEW_FIELD.count('"download_paths":')==1
 assert 'can_access_purchased_digital_item' in NEW
 assert 'reverse("mpw_commerce:download"' in NEW
 try:changed(b'def other():\n    pass\n')
 except RuntimeError:pass
 else:raise RuntimeError('Drift guard missing')
 print('MPW_STATUS_LOCAL_SELFTEST=PASS')

if __name__=='__main__':
 if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest()
 elif len(sys.argv)==2 and sys.argv[1]=='preview':preview()
 elif len(sys.argv)==3 and sys.argv[1] in ('publish','verify','rollback'):
  {'publish':publish,'verify':verify,'rollback':rollback}[sys.argv[1]](sys.argv[2])
 else:raise SystemExit('selftest|preview|publish RUN_ID|verify RUN_ID|rollback RUN_ID')
