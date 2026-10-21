#!/usr/bin/env python3
"""Read-only exact buyer-path view and storefront implementation inspection."""
import os,sys,inspect,re,json
from pathlib import Path
app=Path("/home/zomorod2/Saeit-staging")
if not (app/"manage.py").is_file():raise SystemExit("APP_MISSING")
os.chdir(app);sys.path.insert(0,str(app))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
import django;django.setup()
from django.urls import resolve
from core.models import Product
p=Product.objects.get(pk=879)
print("ATELIER_BUY_PATH_PRODUCT="+json.dumps({"active":p.active,"price":str(p.price),"product_type":p.product_type,"metadata_flags":{k:p.metadata.get(k) for k in ["checkout_enabled","payment_live","sales_enabled","quality_approved","catalog_state","digital_delivery"]}}))
for route in ["/store/","/store/product/879/","/store/product/879/checkout/"]:
    match=resolve(route)
    view=match.func
    module=getattr(view,"__module__","")
    qual=getattr(view,"__qualname__","")
    sourcefile=inspect.getsourcefile(view) or ""
    print("ATELIER_ROUTE="+json.dumps({"route":route,"view":module+"."+qual,"file_relative":str(Path(sourcefile).relative_to(app)) if sourcefile.startswith(str(app)) else Path(sourcefile).name}))
    try:
        source=inspect.getsource(view).splitlines()
    except Exception as exc:
        print("ATELIER_SOURCE_UNAVAILABLE="+type(exc).__name__);continue
    selected=[]
    terms=("template","render(","checkout","purchase","cart","metadata","payment","active","store","contact","login","redirect","product")
    for n,line in enumerate(source,1):
        if any(t in line.lower() for t in terms):
            if any(t in line.lower() for t in ("token","secret","password","key=")):continue
            selected.append({"line":n,"text":line.strip()[:180]})
    print("ATELIER_VIEW_KEYLINES="+json.dumps({"route":route,"code_lines":len(source),"matches":selected[:60]}))

from importlib import import_module
for fpath in ["brands/mojplaywin/product.html","brands/mojplaywin/store.html"]:
    candidate=app/"templates"/fpath
    if candidate.is_file():
        lines=candidate.read_text(encoding="utf8",errors="replace").splitlines()
        hits=[{"n":i+1,"text":line[:260]} for i,line in enumerate(lines) if any(term in line.lower() for term in ("contact","checkout","purchase","href","product","store"))]
        print("ATELIER_TEMPLATE="+json.dumps({"path":fpath,"lines":len(lines),"matches":hits[:60]}))
    else:
        print("ATELIER_TEMPLATE_MISSING="+fpath)
for dotted in ["core.brand_views.branded_store_dispatch","mpw_commerce.product_checkout_page.product_checkout_page"]:
    try:
        module,fnname=dotted.rsplit(".",1)
        fn=getattr(import_module(module),fnname)
        code=inspect.getsource(fn).splitlines()
        matches=[{"line":i+1,"text":line.strip()[:230]} for i,line in enumerate(code) if any(word in line.lower() for word in ("checkout","product","render(","template","available","enabled","price","redirect","login","asset","ready","order","address")) and not any(s in line.lower() for s in ("password","token","secret","private_key"))]
        print("ATELIER_EXTRA_VIEW="+json.dumps({"name":dotted,"total_lines":len(code),"matches":matches[:90]}))
    except Exception as ex:
        print("ATELIER_EXTRA_VIEW_ERR="+json.dumps({"name":dotted,"type":type(ex).__name__}))

from config import urls as urlconf
for fn in ["branded_store_dispatch"]:
    try:
        obj=getattr(urlconf,fn)
        code=inspect.getsource(obj).splitlines()
        hits=[{"line":i+1,"text":l.strip()[:220]} for i,l in enumerate(code) if any(t in l.lower() for t in ("render","store","product","template","brand","checkout"))]
        print("ATELIER_STORE_DISPATCH="+json.dumps({"sourcefile":str(Path(inspect.getsourcefile(obj) or "").name),"total_lines":len(code),"matches":hits[:80]}))
    except Exception as e:print("ATELIER_STORE_DISPATCH_ERROR="+type(e).__name__)
from mpw_commerce.product_checkout_page import approved_for_checkout
src=inspect.getsource(approved_for_checkout).splitlines()
print("ATELIER_CHECKOUT_ELIGIBILITY_SOURCE="+json.dumps([l.strip()[:220] for l in src][:90]))
for root in [app/"templates",app/"core"/"templates",app/"mpw_commerce"/"templates"]:
    if root.exists():
        for pattern in ["product.html","product_checkout.html","store.html"]:
            for file in root.rglob(pattern):
                try:
                    rel=str(file.relative_to(app))
                    lines=file.read_text(encoding="utf8",errors="replace").splitlines()
                    hits=[{"n":i+1,"text":line.strip()[:250]} for i,line in enumerate(lines) if any(t in line.lower() for t in ("checkout","purchase","contact","product","href","form","price","sale"))]
                    print("ATELIER_DISCOVERED_TEMPLATE="+json.dumps({"file":rel,"lines":len(lines),"matches":hits[:75]}))
                except Exception as e:print("ATELIER_TEMPLATE_ERR="+type(e).__name__)

module=import_module("mpw_commerce.product_checkout_page")
print("ATELIER_GATE_FLAG_STATES="+json.dumps({"FLAGS":list(getattr(module,"FLAGS",())),"approvals":list(getattr(module,"APPROVAL_FLAGS",())),"gate_result_with_anonymous":bool(approved_for_checkout(type("FakeRequest",(),{"is_secure":lambda self:True,"get_host":lambda self:"mojplaywin.com","user":type("Guest",(),{"is_authenticated":False,"is_active":True})()})(),p))}))
print("ATELIER_EXISTING_KNOWLEDGE_ASSOC="+json.dumps({"article_attached":p.knowledge_article_id is not None,"article_published":bool(getattr(p.knowledge_article,"published",False)) if p.knowledge_article_id else False,"owner_id_present":p.owner_id is not None}))
for fn_name in ["_private_file","approved_for_checkout"]:
    fn=getattr(module,fn_name,None)
    if fn:
        lines=inspect.getsource(fn).splitlines()
        print("ATELIER_COMMERCE_INVARIANT="+json.dumps({"fn":fn_name,"lines":[l.strip()[:220] for l in lines[:115]]}))
import core.cryptopay_checkout as cryptopay_checkout
for dotted in ["mpw_commerce.downloads.download","mpw_commerce.api_checkout.create_order"]:
    try:
        mm,n=dotted.rsplit(".",1); f=getattr(import_module(mm),n)
        lines=inspect.getsource(f).splitlines()
        print("ATELIER_COMMERCE_FUNCTION="+json.dumps({"name":dotted,"lines":len(lines),"match":[l.strip()[:190] for l in lines if any(w in l.lower() for w in ("pdf","zip","file","product","approval","purchase","type","content"))][:50]}))
    except Exception as e:print("ATELIER_COMMERCE_FUNCTION_MISSING="+json.dumps({"fn":dotted,"err":type(e).__name__}))
print("ATELIER_PRODUCT_TYPE_CHOICES="+json.dumps(Product._meta.get_field("product_type").choices))

from django.conf import settings
from mpw_commerce import product_checkout_page as pc_module
suffixes=approved_for_checkout.__globals__["_private_file"].__globals__.get("ACCEPTED_SUFFIXES",())
root=getattr(settings,"MPW_COMMERCE_PRIVATE_ASSET_ROOT",None)
print("ATELIER_COMMERCE_SUFFIX_ROOT="+json.dumps({"suffixes":sorted(str(z) for z in suffixes),"root_configured":isinstance(root,str) and root.startswith("/"),"root_exists":isinstance(root,str) and Path(root).is_dir(),"zip_supported":".zip" in pc_module.ACCEPTED_SUFFIXES}))
KnowledgeArticle=Product._meta.get_field("knowledge_article").remote_field.model
print("ATELIER_ARTICLE_MODEL_FIELDS="+json.dumps([f.name for f in KnowledgeArticle._meta.fields]))
print("ATELIER_PREVIOUS_PRODUCT_INVENTORY="+json.dumps([{"id":q.pk,"type":q.product_type,"article":q.knowledge_article_id is not None,"approved":all(q.metadata.get(k) is True for k in pc_module.APPROVAL_FLAGS),"price":str(q.price)} for q in Product.objects.filter(pk__in=[72,225,879])]))
print("ATELIER_READONLY_VIEW_INSPECT=PASS")
