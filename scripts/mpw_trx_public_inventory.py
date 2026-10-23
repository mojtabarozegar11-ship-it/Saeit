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
from mpw_commerce.product_checkout_page import product_checkout_page
from mpw_commerce.purchase_history import purchased_downloads
print('CHECKOUT_VIEW='+inspect.getsource(product_checkout_page))
print('HISTORY_VIEW='+inspect.getsource(purchased_downloads))
import hashlib
for rel in ['services/mpw_walletless_commercial_intent.py','services/mpw_trx_commercial_context.py','scripts/mpw_trx_commercial_reconcile_cron.py','services/mpw_trx_commercial_web.py','services/mpw_trx_walletless_checkout_ui.py']:
 print('SOURCE_HASH='+rel+':'+hashlib.sha256((root/rel).read_bytes()).hexdigest())

from django.urls import resolve
for route in ["/store/product/72/", "/store/product/225/", "/store/product/879/", "/commerce/trx-easy/"]:
 match=resolve(route)
 print("LIVE_ROUTE="+json.dumps({"path":route,"view_module":match.func.__module__,"view_name":match.func.__name__,"source_file":inspect.getsourcefile(match.func)},sort_keys=True))
 if route=="/store/product/72/": print("BRANDED_PRODUCT_VIEW_SOURCE="+inspect.getsource(match.func))
print("OUTBOUND_CONFIG="+json.dumps({"smtp_host_configured":bool(getattr(settings,"EMAIL_HOST","")),"smtp_user_configured":bool(getattr(settings,"EMAIL_HOST_USER","")),"from_address_configured":bool(getattr(settings,"DEFAULT_FROM_EMAIL","")),"openai_api_key_configured":bool(os.getenv("OPENAI_API_KEY")),"chat_model_configured":bool(os.getenv("OPENAI_CHAT_MODEL"))},sort_keys=True))

for pk in (72,225,879):
 p=Product.objects.get(pk=pk); meta=p.metadata if isinstance(p.metadata,dict) else {}
 safe={k:meta[k] for k in ("summary","description","seo_description","seo_keywords","keywords","image","seo_image","language","file_type","license","contents","features") if k in meta and isinstance(meta[k],(str,list,dict))}
 for k,v in list(safe.items()):
  if isinstance(v,str): safe[k]=v[:1600]
 print("PUBLIC_SEO_METADATA="+json.dumps({"id":pk,"fields":safe},ensure_ascii=False,sort_keys=True))
for rel in ["core/templates/brands/mojplaywin/product.html"]:
 path=root/rel
 if path.is_file():
  print("PRODUCT_TEMPLATE="+rel)
  print("PRODUCT_TEMPLATE_FULL_SOURCE="+path.read_text()[:30000])
  for line in path.read_text()[:30000].splitlines():
   if any(token in line.lower() for token in ("description","og:","json-ld","product_schema_json","product.title","product.metadata")): print("PRODUCT_TEMPLATE_LINE="+line[:2000])
match=resolve("/sitemap.xml")
print("PUBLIC_SITEMAP_ROUTE="+json.dumps({"view_module":match.func.__module__,"view_name":match.func.__name__,"source_file":inspect.getsourcefile(match.func)},sort_keys=True))
print("PUBLIC_SITEMAP_VIEW_SOURCE="+inspect.getsource(match.func)[:30000])
