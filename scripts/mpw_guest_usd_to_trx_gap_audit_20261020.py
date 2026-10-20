#!/usr/bin/env python3
import os,sys,ast,json,inspect
from pathlib import Path
root=Path('/home/zomorod2/Saeit-staging')
assert root.is_dir() and not root.is_symlink()
os.chdir(root);sys.path.insert(0,str(root));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from django.conf import settings
from django.urls import resolve
from django.apps import apps
for path in ('/store/product/72/checkout/','/store/product/225/checkout/'):
    target=resolve(path).func
    print('MPW_GUEST_RESOLVER='+json.dumps({'path':path,'module':target.__module__,'fn':getattr(target,'__name__','unknown')}))
for name in ('CommerceOrder','CommerceInvoice','CommerceReceipt','CommerceEntitlement','CommerceDownload','CommerceCustomer'):
    try:
        model=apps.get_model('mpw_commerce',name)
        fields=[]
        for f in model._meta.fields:
            fields.append({'name':f.name,'type':f.get_internal_type(),'null':f.null,'blank':f.blank,'unique':f.unique,'default':f.has_default()})
        print('MPW_GUEST_MODEL='+json.dumps({'model':name,'fields':fields}))
    except LookupError:pass
# Print only specific AST functions and neutral identifiers, never wallet addresses, keys or account values.
for rel in ('mpw_commerce/product_checkout_page.py','mpw_commerce/checkout_views.py','mpw_commerce/buyer_orders.py','mpw_commerce/invoicing.py','mpw_commerce/models.py','mpw_commerce/urls.py'):
    path=root/rel
    if not path.is_file():continue
    tree=ast.parse(path.read_text('utf8','replace'))
    fns=[]
    for obj in tree.body:
        if isinstance(obj,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(n in obj.name for n in ('checkout','order','invoice','guest','login','download','quote')):
            # Only short control-flow lines, no literal values or secrets.
            calls=[]
            for n in ast.walk(obj):
                if isinstance(n,ast.Call):
                    f=ast.unparse(n.func)
                    if not any(x in f.lower() for x in ('secret','token','address','wallet','credential','key','password','print','request.')):
                        calls.append(f[:100])
            fns.append({'name':obj.name,'line':obj.lineno,'params':[a.arg for a in obj.args.args],'calls':sorted(set(calls))[:22]})
    print('MPW_GUEST_SOURCE='+json.dumps({'file':rel,'functions':fns[:28]}))
providers={}
for name in ('NOWPAYMENTS_API_KEY','NOWPAYMENTS_IPN_SECRET','TRANSAK_API_KEY','MOONPAY_API_KEY','PAYMEGATE_API_KEY','FIAT_ONRAMP_PROVIDER','USD_CARD_PROVIDER','MPW_FIAT_TO_TRX_ENABLED'):
    providers[name]={'configured':bool(getattr(settings,name,None))}
print('MPW_GUEST_FIAT_PROVIDER_READINESS='+json.dumps(providers))
print('MPW_GUEST_DIAGNOSTIC_READONLY_COMPLETE=true')
