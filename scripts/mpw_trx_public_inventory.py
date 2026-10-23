import os,sys,json,inspect,subprocess
from pathlib import Path
root=Path('/home/zomorod2/Saeit-staging')
os.chdir(root);sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from core.models import Product
from mpw_commerce.buyer_orders import _eligible
from mpw_commerce.downloads import _private_file
from types import SimpleNamespace
print('ELIGIBILITY_SOURCE='+inspect.getsource(_eligible))
for rel in ['mpw_commerce/templates/mpw_commerce/product_checkout.html','mpw_commerce/urls.py']:
 print('SOURCE='+rel+'\n'+(root/rel).read_text()[:20000])
print('PRODUCT_FIELDS='+json.dumps([f.name for f in Product._meta.fields]))
items=[]
for p in Product.objects.filter(active=True,currency='USD')[:1000]:
 if _eligible(p):
  try:
   f=_private_file(SimpleNamespace(product=p));ready=f.is_file() and not f.is_symlink() and f.stat().st_size>0
  except Exception: ready=False
  items.append({'id':p.pk,'title':str(getattr(p,'title',getattr(p,'name',''))),'price':str(p.price),'file_ready':ready})
print('ELIGIBLE_PRODUCTS='+json.dumps(items))
print('FLAGS='+json.dumps({n:getattr(settings,n,None) for n in ['DEBUG','MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_DOWNLOADS_ENABLED','MPW_WALLETLESS_TRX_PUBLIC_ENABLED','MPW_WALLETLESS_TRX_MERCHANT_CANARY_PASSED']}))
r=subprocess.run(['crontab','-l'],capture_output=True,text=True)
print('TRX_CRON_PRESENT='+str('mpw_trx_commercial_reconcile_cron.py' in r.stdout))
