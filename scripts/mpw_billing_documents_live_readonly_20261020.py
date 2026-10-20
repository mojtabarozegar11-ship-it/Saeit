#!/usr/bin/env python3
"""Read-only live MojPlayWin invoice/receipt/fulfillment contract inventory.

No order, customer, invoice, receipt or financial records modified.
No addresses, transaction hashes, account identifiers or credentials printed.
"""
import ast,hashlib,inspect,json,os,sys
from pathlib import Path
APP=Path('/home/zomorod2/Saeit-staging')
assert APP.is_dir() and not APP.is_symlink()
os.chdir(APP);sys.path.insert(0,str(APP))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.apps import apps
from django.urls import get_resolver,URLResolver,URLPattern
from django.conf import settings
from django.template.loader import get_template,TemplateDoesNotExist
from core.models import Order,LedgerEntry
from mpw_commerce.models import CommerceInvoice,CommerceReceipt,CommerceFulfillment
def show(name,value):
 print(name+'='+json.dumps(value,ensure_ascii=False,sort_keys=True,default=str))
show('MPW_BILLING_COUNTS',{
 'orders':Order.objects.count(),
 'invoices':CommerceInvoice.objects.count(),
 'receipts':CommerceReceipt.objects.count(),
 'paid_invoices':CommerceInvoice.objects.filter(status='paid').count(),
 'payment_ledger_rows':LedgerEntry.objects.filter(entry_type='payment').count(),
 'fulfillments':CommerceFulfillment.objects.count()})
for name in ('MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_CUSTOMER_HTTP_ENABLED',
 'MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_SETTLEMENT_ENABLED',
 'MPW_COMMERCE_REAL_RPC_ENABLED','MPW_COMMERCE_AUTORECONCILE_ENABLED',
 'MPW_COMMERCE_DOWNLOADS_ENABLED','MPW_COMMERCE_BUYER_SIGNATURE_ENABLED'):
 show('MPW_BILLING_GATE',{'name':name,'enabled':getattr(settings,name,False) is True})
routes=[]
def crawl(patterns,prefix=''):
 for x in patterns:
  path=prefix+str(x.pattern)
  if isinstance(x,URLResolver):crawl(x.url_patterns,path)
  elif isinstance(x,URLPattern) and any(k in path.lower() for k in
   ('commerce','checkout','receipt','invoice','download')):
   routes.append({'route':path[:150],'name':x.name,
    'module':inspect.unwrap(x.callback).__module__})
crawl(get_resolver().url_patterns)
show('MPW_BILLING_ROUTES',routes[:85])
for module_name,selected in {
 'mpw_commerce.checkout_views':('checkout_invoice','checkout_status'),
 'mpw_commerce.invoicing':('reserve_order_invoice',),
 'mpw_commerce.settlement':('settle_order_invoice',),
 'mpw_commerce.entitlements':('can_access_purchased_digital_item',),
 'mpw_commerce.downloads':('download_paid_item',)
}.items():
 module=__import__(module_name,fromlist=['_'])
 p=Path(module.__file__)
 source=p.read_text('utf8','replace')
 tree=ast.parse(source)
 functions=[]
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in selected:
   calls=[ast.unparse(c.func) for c in ast.walk(n) if isinstance(c,ast.Call)]
   functions.append({'function':n.name,'uses_verified_receipt':'CommerceReceipt' in source[n.col_offset:n.col_offset+0] or any('CommerceReceipt' in c for c in calls),
     'calls_blockchain_verifier':any('trusted_chain_verifier' in c or 'verify_with_trusted_rpc' in c for c in calls),
     'queries_database':any('objects.' in c for c in calls)})
 show('MPW_BILLING_MODULE',{'module':module_name,
  'sha256':hashlib.sha256(source.encode()).hexdigest(),'functions':functions})
for name in ('mpw_commerce/invoice.html','mpw_commerce/receipt.html',
 'mpw_commerce/product_checkout.html','mpw_commerce/purchased_downloads.html'):
 try:get_template(name);exists=True
 except TemplateDoesNotExist:exists=False
 show('MPW_BILLING_TEMPLATE',{'name':name,'exists':exists})
file=APP/'mpw_commerce/templates/mpw_commerce/product_checkout.html'
if file.is_file() and not file.is_symlink():
 source=file.read_text('utf8','replace')
 show('MPW_BILLING_BUYER_JS',{'invoice_endpoint':'/commerce/checkout/invoice/' in source,
  'status_endpoint':'/commerce/checkout/status/' in source,
  'receipt_page_link':'/commerce/receipt/' in source,
  'invoice_page_link':'/commerce/invoice/' in source,
  'receipt_url_binding':'receipt_url' in source,
  'uses_eth_and_trx':'ETH' in source and 'TRX' in source})
print('MPW_BILLING_SOURCE_READONLY=PASS')
