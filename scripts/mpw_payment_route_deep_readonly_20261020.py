#!/usr/bin/env python3
"""Read-only routed checkout, invoice and private-download diagnosis. Never prints credentials."""
import os,sys,ast,json,inspect
from pathlib import Path
root=Path('/home/zomorod2/Saeit-staging')
assert root.is_dir() and not root.is_symlink()
os.chdir(root);sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.urls import resolve
from django.apps import apps
from django.db import connection
from core.models import Product
paths=['/store/product/72/checkout/','/store/product/225/checkout/','/accounts/login/','/accounts/register/']
for path in paths:
    found=resolve(path)
    target=inspect.unwrap(found.func)
    print('BUYER_ROUTE='+json.dumps({'path':path,'module':target.__module__,'name':target.__name__},sort_keys=True))
prods=[]
for i in (72,225):
    p=Product.objects.get(pk=i)
    md=p.metadata or {}
    prods.append({'id':i,'published':bool(p.active),'price_usd':str(p.price),
      'flags':{k:md.get(k) is True for k in ('checkout_enabled','payment_live','asset_verified','license_verified','quality_approved','rights_cleared','factory_publication_permission')},
      'metadata_keys_safe':sorted([k for k in md if not any(x in k.lower() for x in ('wallet','key','secret','path','address','token','hash','credential','seed'))])[:35]})
print('BUYER_PUBLISHED_PRODUCTS='+json.dumps(prods))
names=['CommerceOrder','CommerceCart','CommerceInvoice','CommerceReceipt','CommerceRate','CommerceEntitlement','CommerceDownload']
for name in names:
    try:
        model=apps.get_model('mpw_commerce',name)
        print('BUYER_MODEL='+json.dumps({'name':name,'count':model.objects.count(),'fields':[f.name for f in model._meta.fields]}))
    except LookupError:pass
for nm in ('MPW_COMMERCE_RELEASE_READY','MPW_COMMERCE_CUSTOMER_HTTP_ENABLED','MPW_COMMERCE_INVOICING_ENABLED','MPW_COMMERCE_SETTLEMENT_ENABLED','MPW_COMMERCE_REAL_RPC_ENABLED','MPW_COMMERCE_AUTORECONCILE_ENABLED','MPW_COMMERCE_DOWNLOADS_ENABLED','MPW_COMMERCE_BUYER_SIGNATURE_ENABLED'):
    print('BUYER_GATE='+json.dumps({'name':nm,'enabled':getattr(settings,nm,False) is True}))
modules={
'core/cryptopay_checkout.py':['checkout','product_delivery_ready','private_download'],
'mpw_commerce/product_checkout_page.py':['approved_for_checkout','product_checkout_page'],
'mpw_commerce/buyer_orders.py':['create_digital_order','_eligible'],
'mpw_commerce/invoicing.py':['reserve_order_invoice'],
'mpw_commerce/auto_reconcile.py':['reconcile_invoice','reconcile_pending_invoices'],
'mpw_commerce/checkout_views.py':['checkout_status'],
'mpw_commerce/settlement.py':['settle_order_invoice','_verify_evidence'],
'mpw_commerce/downloads.py':['download_paid_item'],
}
ALLOWED_STR={'GET','POST','paid','pending','confirmed','enabled','ready','active','http','https','TRON','ETH','TRX','USDT','BTC','USD','token','product','order','invoice','receipt','checkout','status','commerce','payment','download','customer','crypto','url','asset','error','id','txid','method'}
class HideLiteral(ast.NodeTransformer):
    def visit_Constant(self,node):
        if isinstance(node.value,str):
            s=node.value
            if len(s)>55 or s.lower().startswith(('0x','tr','sk_','api_','https://','http://','t')) and len(s)>27 or any(t in s.lower() for t in ('password','private','credential','mnemonic','secret','authorization','bearer','wallet_address','receiving_address','rpc_url')):
                return ast.copy_location(ast.Constant(value='[REDACTED_LITERAL]'),node)
        return node
for rel,names in modules.items():
    f=root/rel
    if not f.is_file() or f.is_symlink():
        print('BUYER_MODULE='+json.dumps({'path':rel,'missing':True}))
        continue
    tree=ast.parse(f.read_text('utf8','replace'))
    for fn in tree.body:
        if isinstance(fn,ast.FunctionDef) and fn.name in names:
            new=HideLiteral().visit(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])))
            content=ast.unparse(new)
            # Output only bounded code no comments, no live secrets or addresses.
            if len(content)>13500:content=content[:13500]+' [TRUNCATED]'
            print('BUYER_FUNCTION='+json.dumps({'module':rel,'name':fn.name,'body':content},ensure_ascii=False))
print('BUYER_READONLY_DIAGNOSTIC=PASS')
