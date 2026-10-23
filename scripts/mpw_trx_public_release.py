"""Owner-authorized public TRX activation with transactional QA and file rollback.
No transfer is broadcast. Canary evidence is neither set nor synthesized.
"""
import os,sys,json,hashlib,shutil,tempfile,subprocess,time,urllib.request,zipfile
from pathlib import Path
APP=Path('/home/zomorod2/Saeit-staging')
PUBLIC=Path('/home/zomorod2/mojplaywin.com')
PYTHON='/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python'
EXPECTED={
 'services/mpw_walletless_commercial_intent.py':'53f2b0eb838c20795ac03525de0d56665c4d0f3ac73def3f657647cee7e51727',
 'services/mpw_trx_commercial_context.py':'a6479b7802f34f079b840ae42d88df3df79295a8a38045635bc214ec957f4f02',
 'scripts/mpw_trx_commercial_reconcile_cron.py':'cd5a7a60b2692c2cdb5da80ddb87e8f4a2fa2213cb667e8dfb9809b1f8179bec',
 'services/mpw_trx_commercial_web.py':'a4ccf0fae59672f13b025804d355bb9f2908dbfce409b3ad6ebac85240f9dd70',
}
QR_WHEEL_SHA256='28c7d081ed0cf935e0411293a465efd4d500704072cdb039778a2ab8736190c7'
MODULES=[*EXPECTED,'services/mpw_trx_public_pages.py']
TEMPLATE='mpw_commerce/templates/mpw_commerce/product_checkout.html'
SETTINGS='config/settings.py'
URLS='config/urls.py'
MARK='MPW_PUBLIC_TRX_CUSTOMERS_20261023'
NEW_MAIN='''
{% if mpw_trx_easy_enabled %}
<section data-gateway="trx-public-v1">
<small>MOJPLAYWIN · SECURE DIGITAL CHECKOUT</small>
<h1>{{ product.title }}</h1>
<p class="price">${{ price_usd }} USD</p>
<p>Pay with TRX on the TRON network. Your invoice shows the exact TRX amount and the receiving address.</p>
<div class="panel"><strong>Simple, automatic payment</strong><p>No sender address registration or wallet connection is needed. Open Trust Wallet, use another TRON wallet, or scan the QR on your invoice. Confirm the transfer in your wallet.</p></div>
<form method="post" action="/commerce/trx-easy/start/{{ product.pk }}/">{% csrf_token %}<button type="submit">Create invoice and pay with TRX</button></form>
<p>Send the exact amount only once and before the invoice expires. Network fees are extra. Do not send USDT or a payment on another network.</p>
<p>Your private download unlocks after blockchain confirmation. You can return to <a href="/commerce/trx-easy/purchases/">My TRX purchases</a> to recover your download.</p>
<p><a href="/commerce/trx-easy/">Back to products</a> · <a href="/support/">Purchase support</a> · <a href="/terms/">Terms</a></p>
</section>
{% else %}
'''
CONFIG='''
# MPW_PUBLIC_TRX_CUSTOMERS_20261023
# Explicit owner-authorized launch, not a claim of a completed mainnet test.
MPW_WALLETLESS_TRX_PUBLIC_RELEASE_AUTHORIZED = True
MPW_TRX_PUBLIC_PRODUCT_IDS = (72, 225, 879)
MPW_WALLETLESS_TRX_PUBLIC_ENABLED = _mpw_trx_os.environ.get("MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "0") == "1"
'''
ROUTES='''
# MPW_PUBLIC_TRX_CUSTOMERS_20261023
from services.mpw_trx_public_pages import public_shop as _trx_shop, purchases as _trx_purchases, product_checkout as _trx_product
urlpatterns = [
    path("commerce/trx-easy/", _trx_shop, name="mpw_trx_public_shop"),
    path("commerce/trx-easy/purchases/", _trx_purchases, name="mpw_trx_public_purchases"),
    path("commerce/book/<int:product_id>/", _trx_product, name="mpw_trx_public_product"),
    path("store/product/<int:product_id>/checkout/", _trx_product, name="mpw_trx_public_product_store"),
] + urlpatterns
'''
SMOKE=r'''
import os,json,secrets
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.db import transaction,connection
from django.test import Client
from django.contrib.auth import get_user_model
from services.mpw_walletless_commercial_intent import _commercial_db
from services.mpw_trx_commercial_chain import read_only_independent_pair
from services.mpw_trx_commercial_web import _configured_receiver
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.downloads import _private_file
from core.models import Product
from types import SimpleNamespace
_commercial_db(settings,connection)
assert settings.MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED is False
assert _configured_receiver()=='THFNU1iEXHd71WjEgjqUksd2UnMg2pUi73'
read_only_independent_pair()
for pk in settings.MPW_TRX_PUBLIC_PRODUCT_IDS:
 p=Product.objects.get(pk=pk);assert _eligible(p)
 f=_private_file(SimpleNamespace(product=p));assert f.is_file() and not f.is_symlink() and f.stat().st_size>0
c=Client(enforce_csrf_checks=True)
kw={'secure':True,'HTTP_HOST':'mojplaywin.com'}
r=c.get('/commerce/trx-easy/',**kw);assert r.status_code==200
with transaction.atomic():
 U=get_user_model()
 data={U.USERNAME_FIELD:'mpw-automatic-qa-'+secrets.token_hex(8),'is_active':True,'is_staff':False,'is_superuser':False,'password':'!'}
 u=U.objects.create(**data)
 c.force_login(u)
 r=c.get('/commerce/book/72/',**kw);assert r.status_code==200,r.status_code
 assert b'trx-public-v1' in r.content and b'Connect wallet and request' not in r.content
 assert c.post('/commerce/trx-easy/start/72/',**kw).status_code==403
 token=c.cookies['csrftoken'].value
 r=c.post('/commerce/trx-easy/start/72/',HTTP_X_CSRFTOKEN=token,HTTP_ORIGIN='https://mojplaywin.com',**kw)
 assert r.status_code==302,r.status_code
 invoice_url=r['Location'];assert '/commerce/trx-easy/invoice/' in invoice_url
 invoice_id=int(invoice_url.rstrip('/').split('/')[-1])
 r=c.get(invoice_url,**kw);assert r.status_code==200
 assert b'mpw-open-trustwallet' in r.content and b'data-reconcile-url' in r.content
 r=c.get(f'/commerce/trx-easy/status/{invoice_id}/',**kw);assert r.status_code==200 and not r.json()['can_download']
 assert c.get(f'/commerce/trx-easy/download/{invoice_id}/',**kw).status_code==404
 assert c.get('/commerce/trx-easy/purchases/',**kw).status_code==200
 c.logout()
 data[U.USERNAME_FIELD]='mpw-automatic-other-'+secrets.token_hex(8)
 other=U.objects.create(**data);c.force_login(other)
 assert c.get(f'/commerce/trx-easy/status/{invoice_id}/',**kw).status_code==404
 transaction.set_rollback(True)
print('PUBLIC_TRX_AUTOMATED_QA='+json.dumps({'ordinary_customer_invoice':True,'sender_registration_required':False,'csrf_enforced':True,'unpaid_download_denied':True,'other_buyer_denied':True,'production_qa_rolled_back':True,'mainnet_payment_proved':False}))
'''

def put(path,data):
 if path.is_symlink(): raise RuntimeError('Symlink target')
 tmp=path.with_name(path.name+'.public-trx-tmp')
 if tmp.exists() or tmp.is_symlink(): raise RuntimeError('Concurrent deployment')
 tmp.write_bytes(data);os.chmod(tmp,path.stat().st_mode&0o777 if path.exists() else 0o644);os.replace(tmp,path)

def main():
 source=Path(sys.argv[1])
 assert APP.is_dir() and not APP.is_symlink() and source.is_dir() and not source.is_symlink()
 assert "APP='/home/zomorod2/Saeit-staging'" in (PUBLIC/'passenger_wsgi.py').read_text()
 assert MARK not in (APP/SETTINGS).read_text(),'Already activated; inspect before retry'
 for rel,digest in EXPECTED.items():
  assert not (APP/rel).is_symlink() and hashlib.sha256((APP/rel).read_bytes()).hexdigest()==digest,rel+' changed independently'
 for rel in MODULES: compile((source/rel).read_text(),rel,'exec')
 wheel=source/'wheels/segno-1.6.6-py3-none-any.whl'
 assert wheel.is_file() and not wheel.is_symlink() and hashlib.sha256(wheel.read_bytes()).hexdigest()==QR_WHEEL_SHA256,'Pinned QR dependency missing or changed'
 assert not (APP/'segno').exists() and not (APP/'segno').is_symlink(),'Unexpected existing app-local QR module'
 cron=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=20)
 assert cron.returncode==0 and 'mpw_trx_commercial_reconcile_cron.py' in cron.stdout
 template=(APP/TEMPLATE).read_text();assert template.count('<main>')==1 and template.count('</main>')==1 and 'MPW_WALLETLESS_TRX_BUTTON_V1' in template
 backup=Path(tempfile.mkdtemp(prefix='trx-public-',dir='/home/zomorod2/.local/share/mpw-trx-rollbacks'));os.chmod(backup,0o700)
 before={}
 qr_installed=False
 for rel in [*MODULES,TEMPLATE,SETTINGS,URLS]:
  target=APP/rel;assert not target.is_symlink()
  before[rel]=target.read_bytes() if target.exists() else None
  if before[rel] is not None:
   saved=backup/rel;saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(before[rel]);os.chmod(saved,0o600)
 try:
  qr_tmp=APP/'.segno-public-install-tmp'; assert not qr_tmp.exists() and not qr_tmp.is_symlink(); qr_tmp.mkdir(mode=0o700)
  with zipfile.ZipFile(wheel) as archive:
   for info in archive.infolist():
    if info.is_dir(): continue
    if not info.filename.startswith('segno/') or '..' in Path(info.filename).parts or info.file_size>150000: raise RuntimeError('Unexpected QR package member')
    dest=qr_tmp/info.filename; dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700); dest.write_bytes(archive.read(info))
  assert (qr_tmp/'segno/__init__.py').is_file(); os.replace(qr_tmp/'segno',APP/'segno'); shutil.rmtree(qr_tmp); qr_installed=True
  for rel in MODULES: put(APP/rel,(source/rel).read_bytes())
  import re
  modified=template.replace('<main>','<main>'+NEW_MAIN,1).replace('</main>','{% endif %}</main>',1)
  # Legacy wallet linking scripts must not run in the direct-TRX customer flow.
  modified=re.sub(r'(<script\b[^>]*>.*?</script>)',r'{% if not mpw_trx_easy_enabled %}\1{% endif %}',modified,flags=re.S)
  put(APP/TEMPLATE,modified.encode())
  put(APP/URLS,before[URLS]+ROUTES.encode())
  put(APP/SETTINGS,before[SETTINGS]+CONFIG.encode())
  env=os.environ.copy();env['MPW_WALLETLESS_TRX_PUBLIC_ENABLED']='1'
  result=subprocess.run([PYTHON,'-B','-c',SMOKE],cwd=APP,env=env,capture_output=True,text=True,timeout=220)
  if result.returncode or 'PUBLIC_TRX_AUTOMATED_QA=' not in result.stdout:
   print('QA_ERROR='+result.stderr[-3500:]);raise RuntimeError('Ordinary customer automatic QA failed')
  print(result.stdout.strip())
  active=CONFIG.replace('"MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "0"','"MPW_WALLETLESS_TRX_PUBLIC_ENABLED", "1"')
  put(APP/SETTINGS,before[SETTINGS]+active.encode())
  (APP/'tmp').mkdir(exist_ok=True);(APP/'tmp/restart.txt').touch()
  (PUBLIC/'tmp').mkdir(exist_ok=True);(PUBLIC/'tmp/restart.txt').touch()
  ok=False
  for attempt in range(12):
   try:
    with urllib.request.urlopen('https://mojplaywin.com/commerce/trx-easy/?release=20261023',timeout=12) as r:
     body=r.read(200000)
     if r.status==200 and b'Buy digital products with TRX' in body and b'/commerce/book/72/' in body:ok=True;break
   except Exception: pass
   time.sleep(3)
  if not ok: raise RuntimeError('Public HTTPS storefront verification failed')
  result={'status':'PUBLIC_TRX_LIVE','sender_registration_required':False,'product_ids':[72,225,879],'automatic_reconciliation':True,'mainnet_payment_proved':False,'backup_id':backup.name}
  (backup/'release.json').write_text(json.dumps(result));print('PUBLIC_TRX_RELEASE='+json.dumps(result))
 except BaseException:
  if qr_installed: shutil.rmtree(APP/'segno',ignore_errors=True)
  shutil.rmtree(APP/'.segno-public-install-tmp',ignore_errors=True)
  for rel,data in before.items():
   if data is None:(APP/rel).unlink(missing_ok=True)
   else:put(APP/rel,data)
  (APP/'tmp/restart.txt').touch();(PUBLIC/'tmp/restart.txt').touch()
  print('PUBLIC_TRX_ROLLBACK=RESTORED');raise

if __name__=='__main__':main()
